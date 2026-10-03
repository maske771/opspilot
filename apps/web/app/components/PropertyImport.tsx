'use client';

import { useRef, useState } from 'react';
import { ApiError, apiUpload } from '../lib/api';
import { useAuth } from '../lib/auth';
import { useLocale } from '../lib/locale';

type ImportPlan = {
  rows: number;
  properties: { name: string; address: string | null; existing: boolean; new_units: string[] }[];
  properties_new: number;
  properties_existing: number;
  units_new: number;
  units_skipped: number;
  errors: { row: number; code: string }[];
};

// Header names the server accepts in each UI language (see property_import.COLUMNS).
const TEMPLATES: Record<string, string> = {
  en: 'property,address,unit\nSunset Tower,12 Beach Road,101\nSunset Tower,,102\nGarden Villas,,\n',
  ru: 'объект,адрес,квартира\nSunset Tower,12 Beach Road,101\nSunset Tower,,102\nGarden Villas,,\n',
  th: 'อาคาร,ที่อยู่,ห้อง\nSunset Tower,12 Beach Road,101\nSunset Tower,,102\nGarden Villas,,\n',
};

export function PropertyImport({ onImported }: { onImported: () => void }) {
  const { token } = useAuth();
  const { t, tOr, locale } = useLocale();
  const [open, setOpen] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [plan, setPlan] = useState<ImportPlan | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<ImportPlan | null>(null);
  const input = useRef<HTMLInputElement>(null);

  const message = (err: unknown) => (err instanceof ApiError ? tOr(`import.error.${err.message}`, err.message) : t('import.failed'));

  function reset() {
    setFile(null);
    setPlan(null);
    setError(null);
    if (input.current) input.current.value = '';
  }

  async function pick(selected: File | null) {
    reset();
    setDone(null);
    if (!selected) return;
    setFile(selected);
    const form = new FormData();
    form.append('file', selected);
    setBusy(true);
    try {
      setPlan(await apiUpload<ImportPlan>('/properties/import/preview', form, token));
    } catch (err) {
      setError(message(err));
    } finally {
      setBusy(false);
    }
  }

  async function confirm() {
    if (!file) return;
    const form = new FormData();
    form.append('file', file);
    setBusy(true);
    try {
      const result = await apiUpload<ImportPlan>('/properties/import', form, token);
      reset();
      setDone(result);
      onImported();
    } catch (err) {
      setError(message(err));
    } finally {
      setBusy(false);
    }
  }

  function downloadTemplate() {
    // BOM so Excel opens the UTF-8 file with the right encoding.
    const blob = new Blob(['﻿' + (TEMPLATES[locale] ?? TEMPLATES.en)], { type: 'text/csv;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'properties-template.csv';
    a.click();
    URL.revokeObjectURL(url);
  }

  if (!open) {
    return (
      <button type="button" className="btn btn-secondary" style={{ marginBottom: 24 }} onClick={() => setOpen(true)}>
        {t('import.open')}
      </button>
    );
  }

  const canImport = plan && plan.errors.length === 0 && (plan.properties_new > 0 || plan.units_new > 0);

  return (
    <section className="card card-pad" style={{ marginBottom: 24 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: 12 }}>
        <h2 style={{ fontSize: 15, margin: '0 0 6px' }}>{t('import.title')}</h2>
        <button type="button" className="btn btn-ghost" onClick={() => { reset(); setDone(null); setOpen(false); }}>
          {t('common.cancel')}
        </button>
      </div>
      <p style={{ fontSize: 13, color: 'var(--color-text-muted)', margin: '0 0 14px' }}>{t('import.hint')}</p>

      <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
        <input ref={input} type="file" accept=".csv,.xlsx,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" onChange={(e) => pick(e.target.files?.[0] ?? null)} aria-label={t('import.chooseFile')} style={{ display: 'none' }} />
        <button type="button" className="btn btn-secondary" disabled={busy} onClick={() => input.current?.click()}>
          {t('import.chooseFile')}
        </button>
        <button type="button" className="btn btn-ghost" onClick={downloadTemplate}>
          {t('import.template')}
        </button>
        {file && <span style={{ fontSize: 13, color: 'var(--color-text-muted)' }}>{file.name}</span>}
      </div>

      {busy && <p style={{ fontSize: 13, color: 'var(--color-text-muted)' }}>{t('common.loading')}</p>}
      {error && <div style={{ marginTop: 14, color: 'var(--color-danger)', fontSize: 13 }}>{error}</div>}
      {done && (
        <div style={{ marginTop: 14, fontSize: 13.5, color: 'var(--status-completed-text)' }}>
          {t('import.done', { properties: done.properties_new, units: done.units_new })}
        </div>
      )}

      {plan && (
        <div style={{ marginTop: 16 }}>
          <div style={{ fontSize: 13.5, marginBottom: 10 }}>
            {t('import.summary', { rows: plan.rows, properties: plan.properties_new, existing: plan.properties_existing, units: plan.units_new, skipped: plan.units_skipped })}
          </div>
          {plan.errors.length > 0 && (
            <div style={{ padding: 12, borderRadius: 10, background: 'var(--color-danger-soft)', color: 'var(--color-danger)', fontSize: 13, marginBottom: 12 }}>
              <div style={{ fontWeight: 600, marginBottom: 6 }}>{t('import.fixErrors')}</div>
              {plan.errors.slice(0, 20).map((e) => (
                <div key={`${e.row}-${e.code}`}>{t('import.rowError', { row: e.row, error: tOr(`import.error.${e.code}`, e.code) })}</div>
              ))}
              {plan.errors.length > 20 && <div>…</div>}
            </div>
          )}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6, maxHeight: 260, overflowY: 'auto', marginBottom: 14 }}>
            {plan.properties.map((p) => (
              <div key={p.name} style={{ fontSize: 13, display: 'flex', gap: 8, alignItems: 'baseline', flexWrap: 'wrap' }}>
                <span className="badge" style={p.existing ? { background: 'var(--color-bg)', color: 'var(--color-text-muted)' } : { background: 'var(--color-accent-soft)', color: 'var(--color-accent-text)' }}>
                  {p.existing ? t('import.existing') : t('import.new')}
                </span>
                <strong>{p.name}</strong>
                {p.address && <span style={{ color: 'var(--color-text-subtle)' }}>{p.address}</span>}
                {p.new_units.length > 0 && <span style={{ color: 'var(--color-text-muted)' }}>{t('import.unitsCount', { count: p.new_units.length })}</span>}
              </div>
            ))}
          </div>
          <button type="button" className="btn btn-accent" disabled={busy || !canImport} onClick={confirm}>
            {t('import.confirm')}
          </button>
        </div>
      )}
    </section>
  );
}
