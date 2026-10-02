'use client';

import { useCallback, useEffect, useState } from 'react';
import { RequireAuth, useAuth } from '../lib/auth';
import { apiFetch, ApiError, type ServiceRead, type TicketPriority } from '../lib/api';
import { LOCALES, useLocale } from '../lib/locale';
import { isAdminRole } from '../lib/roles';
import { invalidateServices, serviceName } from '../lib/services';
import { PRIORITY_KEYS } from '../lib/ui';

type Draft = { names: Record<string, string>; keywords: string; default_priority: TicketPriority };

const EMPTY_DRAFT: Draft = { names: {}, keywords: '', default_priority: 'medium' };

function toDraft(service: ServiceRead): Draft {
  return { names: { ...service.names }, keywords: service.keywords.join(', '), default_priority: service.default_priority };
}

function toBody(draft: Draft) {
  return {
    names: draft.names,
    keywords: draft.keywords.split(/[,\n]/).map((k) => k.trim()).filter(Boolean),
    default_priority: draft.default_priority,
  };
}

function sameDraft(a: Draft, b: Draft) {
  return JSON.stringify(toBody(a)) === JSON.stringify(toBody(b));
}

function ServiceEditor({
  draft,
  onChange,
  isSystem,
}: {
  draft: Draft;
  onChange: (next: Draft) => void;
  isSystem: boolean;
}) {
  const { t } = useLocale();
  return (
    <>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 10, marginBottom: 10 }}>
        {LOCALES.map((locale) => (
          <label key={locale.code} className="field">
            {t('services.name')} ({locale.label})
            <input
              value={draft.names[locale.code] ?? ''}
              onChange={(e) => onChange({ ...draft, names: { ...draft.names, [locale.code]: e.target.value } })}
              className="input"
            />
          </label>
        ))}
        <label className="field">
          {t('services.defaultPriority')}
          <select
            value={draft.default_priority}
            onChange={(e) => onChange({ ...draft, default_priority: e.target.value as TicketPriority })}
            className="select"
          >
            {Object.entries(PRIORITY_KEYS).map(([value, key]) => (
              <option key={value} value={value}>
                {t(key)}
              </option>
            ))}
          </select>
        </label>
      </div>
      <label className="field">
        {t('services.keywords')}
        <textarea
          value={isSystem ? '' : draft.keywords}
          onChange={(e) => onChange({ ...draft, keywords: e.target.value })}
          className="textarea"
          rows={2}
          disabled={isSystem}
          placeholder={isSystem ? t('services.systemHint') : t('services.keywordsPlaceholder')}
        />
      </label>
    </>
  );
}

function ServiceCard({ service, onSaved }: { service: ServiceRead; onSaved: () => void }) {
  const { token } = useAuth();
  const { t, locale } = useLocale();
  const [draft, setDraft] = useState<Draft>(() => toDraft(service));
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => setDraft(toDraft(service)), [service]);

  async function save() {
    if (!token) return;
    setBusy(true);
    setError(null);
    try {
      const body = toBody(draft);
      await apiFetch(`/services/${service.id}`, {
        method: 'PATCH',
        token,
        body: service.is_system ? { names: body.names, default_priority: body.default_priority } : body,
      });
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
      onSaved();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t('services.saveFailed'));
    } finally {
      setBusy(false);
    }
  }

  async function archive() {
    if (!token || !window.confirm(t('services.archiveConfirm'))) return;
    setBusy(true);
    setError(null);
    try {
      await apiFetch(`/services/${service.id}`, { method: 'DELETE', token });
      onSaved();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t('services.saveFailed'));
      setBusy(false);
    }
  }

  return (
    <div className="card card-pad">
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
        <h2 style={{ fontSize: 15, margin: 0 }}>{serviceName(service, locale, service.code)}</h2>
        {service.is_system && (
          <span className="badge" style={{ background: 'var(--color-bg)', color: 'var(--color-text-muted)' }}>
            {t('services.system')}
          </span>
        )}
      </div>
      {error && <div style={{ color: 'var(--color-danger)', fontSize: 13, marginBottom: 10 }}>{error}</div>}
      <ServiceEditor draft={draft} onChange={setDraft} isSystem={service.is_system} />
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginTop: 12 }}>
        <button type="button" className="btn btn-primary" disabled={busy || sameDraft(draft, toDraft(service))} onClick={save}>
          {t('common.save')}
        </button>
        {!service.is_system && (
          <button type="button" className="btn btn-secondary" disabled={busy} onClick={archive}>
            {t('services.archive')}
          </button>
        )}
        {saved && <span style={{ fontSize: 13, color: 'var(--status-completed-text)' }}>{t('services.saved')}</span>}
      </div>
    </div>
  );
}

function NewServiceCard({ onCreated }: { onCreated: () => void }) {
  const { token } = useAuth();
  const { t } = useLocale();
  const [draft, setDraft] = useState<Draft>(EMPTY_DRAFT);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function create() {
    if (!token) return;
    setBusy(true);
    setError(null);
    try {
      await apiFetch('/services', { method: 'POST', token, body: toBody(draft) });
      setDraft(EMPTY_DRAFT);
      onCreated();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t('services.saveFailed'));
    } finally {
      setBusy(false);
    }
  }

  const hasName = Object.values(draft.names).some((n) => n.trim());

  return (
    <div className="card card-pad" style={{ marginBottom: 20, borderStyle: 'dashed' }}>
      <h2 style={{ fontSize: 15, marginTop: 0, marginBottom: 12 }}>{t('services.addTitle')}</h2>
      {error && <div style={{ color: 'var(--color-danger)', fontSize: 13, marginBottom: 10 }}>{error}</div>}
      <ServiceEditor draft={draft} onChange={setDraft} isSystem={false} />
      <button type="button" className="btn btn-accent" style={{ marginTop: 12 }} disabled={busy || !hasName} onClick={create}>
        {busy ? t('common.adding') : t('services.add')}
      </button>
    </div>
  );
}

function ServicesView() {
  const { token, user } = useAuth();
  const { t } = useLocale();
  const [services, setServices] = useState<ServiceRead[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    if (!token) return;
    invalidateServices();
    apiFetch<ServiceRead[]>('/services', { token })
      .then(setServices)
      .catch((err) => setError(err instanceof Error ? err.message : t('services.loadFailed')));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  useEffect(() => {
    load();
  }, [load]);

  if (!isAdminRole(user?.role)) {
    return (
      <main className="page">
        <div className="empty-state">{t('common.ownerAdminOnly')}</div>
      </main>
    );
  }

  return (
    <main className="page">
      <h1 className="page-title">{t('nav.services')}</h1>
      <p className="page-subtitle">{t('services.subtitle')}</p>

      {error && (
        <div style={{ padding: 14, borderRadius: 10, background: 'var(--color-danger-soft)', color: 'var(--color-danger)', marginBottom: 20 }}>
          {error}
        </div>
      )}

      <NewServiceCard onCreated={load} />

      {!services ? (
        <p style={{ color: 'var(--color-text-muted)' }}>{t('common.loading')}</p>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          {services.map((service) => (
            <ServiceCard key={service.id} service={service} onSaved={load} />
          ))}
        </div>
      )}
    </main>
  );
}

export default function ServicesPage() {
  return (
    <RequireAuth>
      <ServicesView />
    </RequireAuth>
  );
}
