'use client';

import { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { RequireAuth, useAuth } from '../../lib/auth';
import {
  apiFetch,
  ApiError,
  type PropertyRead,
  type PropertyServiceRead,
  type PropertyServicesRead,
  type TicketPriority,
} from '../../lib/api';
import { useLocale } from '../../lib/locale';
import { isAdminRole } from '../../lib/roles';
import { serviceName } from '../../lib/services';
import { PRIORITY_KEYS, priorityBadgeStyle } from '../../lib/ui';

const PRIORITIES: TicketPriority[] = ['critical', 'high', 'medium', 'low'];

// Per service: enabled flag plus raw input strings per priority ('' = inherit).
type Row = { enabled: boolean; sla: Record<TicketPriority, { response: string; resolution: string }> };

function toRows(data: PropertyServicesRead): Record<string, Row> {
  return Object.fromEntries(
    data.services.map((s) => [
      s.service_id,
      {
        enabled: s.enabled,
        sla: Object.fromEntries(
          PRIORITIES.map((p) => [p, { response: String(s.overrides[p]?.response_minutes ?? ''), resolution: String(s.overrides[p]?.resolution_minutes ?? '') }]),
        ) as Row['sla'],
      },
    ]),
  );
}

function ServiceRow({ service, row, onChange }: { service: PropertyServiceRead; row: Row; onChange: (next: Row) => void }) {
  const { t, locale } = useLocale();
  const inherited = (p: TicketPriority) => service.sla.find((s) => s.priority === p && s.source !== 'property') ?? null;
  const effective = (p: TicketPriority) => service.sla.find((s) => s.priority === p)!;

  return (
    <div className="card card-pad">
      <label style={{ display: 'flex', alignItems: 'center', gap: 10, cursor: 'pointer', fontWeight: 600, fontSize: 14 }}>
        <input type="checkbox" checked={row.enabled} onChange={(e) => onChange({ ...row, enabled: e.target.checked })} />
        {serviceName(service, locale, service.code)}
      </label>
      {row.enabled && (
        <div style={{ marginTop: 12 }}>
          <div style={{ display: 'grid', gridTemplateColumns: '110px 1fr 1fr', gap: 10, fontSize: 12, color: 'var(--color-text-muted)', marginBottom: 6 }}>
            <span />
            <span>{t('settings.sla.response')}</span>
            <span>{t('settings.sla.resolution')}</span>
          </div>
          {PRIORITIES.map((p) => {
            const fallback = inherited(p) ?? effective(p);
            const hint = fallback.source === 'organization' ? t('propertyServices.fromOrganization') : t('propertyServices.fromDefault');
            return (
              <div key={p} style={{ display: 'grid', gridTemplateColumns: '110px 1fr 1fr', gap: 10, alignItems: 'center', marginBottom: 6 }}>
                <span className="badge" style={{ ...priorityBadgeStyle(p), width: 'fit-content' }}>
                  {t(PRIORITY_KEYS[p])}
                </span>
                {(['response', 'resolution'] as const).map((field) => (
                  <input
                    key={field}
                    type="number"
                    min={1}
                    max={43200}
                    className="input"
                    value={row.sla[p][field]}
                    title={hint}
                    placeholder={`${field === 'response' ? fallback.response_minutes : fallback.resolution_minutes} · ${hint}`}
                    onChange={(e) => onChange({ ...row, sla: { ...row.sla, [p]: { ...row.sla[p], [field]: e.target.value } } })}
                  />
                ))}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

function PropertyServicesView() {
  const { token, user } = useAuth();
  const { t } = useLocale();
  const { id } = useParams<{ id: string }>();
  const [property, setProperty] = useState<PropertyRead | null>(null);
  const [data, setData] = useState<PropertyServicesRead | null>(null);
  const [rows, setRows] = useState<Record<string, Row>>({});
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const apply = useCallback((next: PropertyServicesRead) => {
    setData(next);
    setRows(toRows(next));
  }, []);

  useEffect(() => {
    if (!token || !id) return;
    apiFetch<PropertyRead>(`/properties/${id}`, { token }).then(setProperty).catch(() => undefined);
    apiFetch<PropertyServicesRead>(`/properties/${id}/services`, { token })
      .then(apply)
      .catch((err) => setError(err instanceof Error ? err.message : t('propertyServices.loadFailed')));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, id]);

  async function save() {
    if (!token || !data) return;
    const services = [];
    for (const service of data.services) {
      const row = rows[service.service_id];
      if (!row?.enabled) continue;
      const sla: Record<string, { response_minutes: number; resolution_minutes: number }> = {};
      for (const p of PRIORITIES) {
        const { response, resolution } = row.sla[p];
        if (!response && !resolution) continue;
        if (!response || !resolution || Number(response) < 1 || Number(resolution) < 1) {
          setError(t('propertyServices.pairIncomplete'));
          return;
        }
        sla[p] = { response_minutes: Number(response), resolution_minutes: Number(resolution) };
      }
      services.push({ service_id: service.service_id, sla });
    }
    setSaving(true);
    setSaved(false);
    setError(null);
    try {
      apply(await apiFetch<PropertyServicesRead>(`/properties/${id}/services`, { method: 'PUT', token, body: { services } }));
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t('propertyServices.saveFailed'));
    } finally {
      setSaving(false);
    }
  }

  if (!isAdminRole(user?.role)) {
    return (
      <main className="page">
        <div className="empty-state">{t('common.ownerAdminOnly')}</div>
      </main>
    );
  }

  return (
    <main className="page">
      <Link href="/properties" style={{ fontSize: 13, color: 'var(--color-text-muted)' }}>
        ← {t('nav.properties')}
      </Link>
      <h1 className="page-title" style={{ marginTop: 8 }}>
        {property?.name ?? '…'} · {t('properties.servicesLink')}
      </h1>
      <p className="page-subtitle">{t('propertyServices.subtitle')}</p>

      {data && !data.configured && (
        <div style={{ padding: 12, borderRadius: 10, background: 'var(--color-accent-soft)', color: 'var(--color-accent-text)', marginBottom: 16, fontSize: 13 }}>
          {t('propertyServices.notConfigured')}
        </div>
      )}
      {error && (
        <div style={{ padding: 12, borderRadius: 10, background: 'var(--color-danger-soft)', color: 'var(--color-danger)', marginBottom: 16, fontSize: 13 }}>
          {error}
        </div>
      )}

      {!data ? (
        <p style={{ color: 'var(--color-text-muted)' }}>{t('common.loading')}</p>
      ) : (
        <>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12, marginBottom: 16 }}>
            {data.services.map((service) => (
              <ServiceRow
                key={service.service_id}
                service={service}
                row={rows[service.service_id]}
                onChange={(next) => setRows((prev) => ({ ...prev, [service.service_id]: next }))}
              />
            ))}
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <button type="button" className="btn btn-accent" disabled={saving} onClick={save}>
              {saving ? t('common.saving') : t('common.save')}
            </button>
            {saved && <span style={{ fontSize: 13, color: 'var(--status-completed-text)' }}>{t('propertyServices.saved')}</span>}
          </div>
        </>
      )}
    </main>
  );
}

export default function PropertyServicesPage() {
  return (
    <RequireAuth>
      <PropertyServicesView />
    </RequireAuth>
  );
}
