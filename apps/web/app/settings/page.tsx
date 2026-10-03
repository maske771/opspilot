'use client';

import { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import { RequireAuth, useAuth } from '../lib/auth';
import { apiFetch, ApiError, type EffectiveSla, type OrganizationRead, type TicketPriority } from '../lib/api';
import { useLocale } from '../lib/locale';
import { isAdminRole } from '../lib/roles';
import { PRIORITY_KEYS, priorityBadgeStyle } from '../lib/ui';

const PRIORITIES: TicketPriority[] = ['critical', 'high', 'medium', 'low'];

function CompanySection() {
  const { token } = useAuth();
  const { t } = useLocale();
  const [name, setName] = useState('');
  const [loaded, setLoaded] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!token) return;
    apiFetch<OrganizationRead>('/organization', { token }).then((org) => {
      setName(org.name);
      setLoaded(org.name);
    });
  }, [token]);

  async function save() {
    if (!token) return;
    setSaving(true);
    setSaved(false);
    setError(null);
    try {
      const updated = await apiFetch<OrganizationRead>('/organization', { method: 'PATCH', token, body: { name } });
      setLoaded(updated.name);
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t('settings.company.saveFailed'));
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="card card-pad" style={{ marginBottom: 20 }}>
      <h2 style={{ fontSize: 15, marginTop: 0, marginBottom: 14 }}>{t('settings.company.title')}</h2>
      {error && (
        <div style={{ padding: 12, borderRadius: 10, background: 'var(--color-danger-soft)', color: 'var(--color-danger)', marginBottom: 14, fontSize: 13 }}>
          {error}
        </div>
      )}
      <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
        <input value={name} onChange={(e) => setName(e.target.value)} className="input" style={{ maxWidth: 360 }} placeholder={t('settings.company.namePlaceholder')} />
        <button type="button" className="btn btn-accent" disabled={saving || !name.trim() || name === loaded} onClick={save}>
          {saving ? t('common.saving') : t('common.save')}
        </button>
        {saved && <span style={{ fontSize: 13, color: 'var(--status-completed-text)' }}>{t('settings.company.saved')}</span>}
      </div>
    </section>
  );
}

function SlaSection() {
  const { token } = useAuth();
  const { t } = useLocale();
  const [rows, setRows] = useState<EffectiveSla[] | null>(null);
  const [draft, setDraft] = useState<Record<TicketPriority, { response: string; resolution: string }>>({} as never);
  const [saving, setSaving] = useState(false);
  const [resetting, setResetting] = useState<TicketPriority | null>(null);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const applyRows = useCallback((data: EffectiveSla[]) => {
    setRows(data);
    setDraft(Object.fromEntries(data.map((r) => [r.priority, { response: String(r.response_minutes), resolution: String(r.resolution_minutes) }])) as never);
  }, []);

  useEffect(() => {
    if (!token) return;
    apiFetch<EffectiveSla[]>('/organization/sla', { token })
      .then(applyRows)
      .catch((err) => setError(err instanceof Error ? err.message : t('settings.sla.loadFailed')));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  function setField(priority: TicketPriority, field: 'response' | 'resolution', value: string) {
    setDraft((prev) => ({ ...prev, [priority]: { ...prev[priority], [field]: value } }));
  }

  function isDirty(priority: TicketPriority): boolean {
    const row = rows?.find((r) => r.priority === priority);
    if (!row) return false;
    return draft[priority]?.response !== String(row.response_minutes) || draft[priority]?.resolution !== String(row.resolution_minutes);
  }

  async function saveChanges() {
    if (!token || !rows) return;
    const body: Record<string, { response_minutes: number; resolution_minutes: number }> = {};
    for (const priority of PRIORITIES) {
      if (!isDirty(priority)) continue;
      const response = Number(draft[priority].response);
      const resolution = Number(draft[priority].resolution);
      if (!Number.isFinite(response) || !Number.isFinite(resolution) || response < 1 || resolution < 1) {
        setError(t('settings.sla.invalidValue'));
        return;
      }
      body[priority] = { response_minutes: response, resolution_minutes: resolution };
    }
    if (Object.keys(body).length === 0) return;
    setSaving(true);
    setSaved(false);
    setError(null);
    try {
      const updated = await apiFetch<EffectiveSla[]>('/organization/sla', { method: 'PATCH', token, body });
      applyRows(updated);
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t('settings.sla.saveFailed'));
    } finally {
      setSaving(false);
    }
  }

  async function resetPriority(priority: TicketPriority) {
    if (!token) return;
    setResetting(priority);
    setError(null);
    try {
      const updated = await apiFetch<EffectiveSla[]>('/organization/sla', { method: 'PATCH', token, body: { [priority]: null } });
      applyRows(updated);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t('settings.sla.saveFailed'));
    } finally {
      setResetting(null);
    }
  }

  const anyDirty = PRIORITIES.some(isDirty);

  return (
    <section className="card card-pad" style={{ marginBottom: 20 }}>
      <h2 style={{ fontSize: 15, marginTop: 0, marginBottom: 4 }}>{t('settings.sla.title')}</h2>
      <p style={{ fontSize: 12.5, color: 'var(--color-text-subtle)', marginTop: 0, marginBottom: 16 }}>{t('settings.sla.desc')}</p>

      {error && (
        <div style={{ padding: 12, borderRadius: 10, background: 'var(--color-danger-soft)', color: 'var(--color-danger)', marginBottom: 14, fontSize: 13 }}>
          {error}
        </div>
      )}

      {!rows ? (
        <p style={{ color: 'var(--color-text-muted)' }}>{t('common.loading')}</p>
      ) : (
        <>
          <div className="sla-grid sla-head" style={{ fontSize: 12, color: 'var(--color-text-muted)', marginBottom: 8 }}>
            <span />
            <span>{t('settings.sla.response')}</span>
            <span>{t('settings.sla.resolution')}</span>
            <span>{t('settings.sla.status')}</span>
            <span />
          </div>
          {rows.map((row) => (
            <div key={row.priority} className="sla-grid" style={{ padding: '8px 0', borderTop: '1px solid var(--color-border-subtle)' }}>
              <span className="badge" style={{ ...priorityBadgeStyle(row.priority), width: 'fit-content' }}>
                {t(PRIORITY_KEYS[row.priority])}
              </span>
              <input
                type="number"
                min={1}
                max={43200}
                className="input"
                value={draft[row.priority]?.response ?? ''}
                onChange={(e) => setField(row.priority, 'response', e.target.value)}
              />
              <input
                type="number"
                min={1}
                max={43200}
                className="input"
                value={draft[row.priority]?.resolution ?? ''}
                onChange={(e) => setField(row.priority, 'resolution', e.target.value)}
              />
              <span style={{ fontSize: 12.5, color: row.is_custom ? 'var(--color-accent-text)' : 'var(--color-text-subtle)' }}>
                {row.is_custom ? t('settings.sla.custom') : t('settings.sla.default')}
              </span>
              <button
                type="button"
                className="btn btn-secondary"
                disabled={!row.is_custom || resetting === row.priority}
                onClick={() => resetPriority(row.priority)}
                style={{ fontSize: 12.5, padding: '6px 10px' }}
              >
                {t('settings.sla.reset')}
              </button>
            </div>
          ))}

          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginTop: 16 }}>
            <button type="button" className="btn btn-accent" disabled={saving || !anyDirty} onClick={saveChanges}>
              {saving ? t('common.saving') : t('common.save')}
            </button>
            {saved && <span style={{ fontSize: 13, color: 'var(--status-completed-text)' }}>{t('settings.sla.saved')}</span>}
          </div>
        </>
      )}
    </section>
  );
}

function RelatedSettings() {
  const { t } = useLocale();
  const items: { href: string; label: string }[] = [
    { href: '/reports/daily', label: t('settings.related.dailyReport') },
    { href: '/channels', label: t('settings.related.channels') },
    { href: '/team', label: t('settings.related.team') },
  ];
  return (
    <section className="card card-pad">
      <h2 style={{ fontSize: 15, marginTop: 0, marginBottom: 14 }}>{t('settings.related.title')}</h2>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        {items.map((item) => (
          <Link key={item.href} href={item.href} style={{ fontSize: 13.5, color: 'var(--color-accent-text)' }}>
            {item.label} →
          </Link>
        ))}
      </div>
    </section>
  );
}

function SettingsView() {
  const { user } = useAuth();
  const { t } = useLocale();

  if (!isAdminRole(user?.role)) {
    return (
      <main className="page">
        <div className="empty-state">{t('common.ownerAdminOnly')}</div>
      </main>
    );
  }

  return (
    <main className="page">
      <h1 className="page-title">{t('nav.settings')}</h1>
      <p className="page-subtitle">{t('settings.subtitle')}</p>

      <CompanySection />
      <SlaSection />
      <RelatedSettings />
    </main>
  );
}

export default function SettingsPage() {
  return (
    <RequireAuth>
      <SettingsView />
    </RequireAuth>
  );
}
