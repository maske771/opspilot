'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { RequireAuth, useAuth } from '../lib/auth';
import { apiFetch, type AuditEventRead, type PropertyRead, type UserRead } from '../lib/api';
import { useAuditText } from '../lib/audit';
import type { MessageKey } from '../lib/i18n/en';
import { useLocale } from '../lib/locale';
import { isAdminRole } from '../lib/roles';

const PAGE_SIZE = 100;
const ENTITY_KEYS: Record<string, MessageKey> = {
  ticket: 'audit.entity.ticket',
  user: 'audit.entity.user',
  channel: 'audit.entity.channel',
  customer: 'audit.entity.customer',
  property: 'audit.entity.property',
  service: 'audit.entity.service',
  organization: 'audit.entity.organization',
};

function AuditView() {
  const { token, user } = useAuth();
  const { t, formatDateTime } = useLocale();
  const [entity, setEntity] = useState('');
  const [events, setEvents] = useState<AuditEventRead[]>([]);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(true);
  const [users, setUsers] = useState<UserRead[]>([]);
  const [properties, setProperties] = useState<PropertyRead[]>([]);
  const describe = useAuditText(users, properties);
  const allowed = isAdminRole(user?.role);

  useEffect(() => {
    if (!token || !allowed) return;
    apiFetch<UserRead[]>('/users', { token }).then(setUsers);
    apiFetch<PropertyRead[]>('/properties', { token }).then(setProperties);
  }, [token, allowed]);

  function fetchPage(offset: number) {
    const query = new URLSearchParams({ limit: String(PAGE_SIZE), offset: String(offset) });
    if (entity) query.set('entity_type', entity);
    return apiFetch<AuditEventRead[]>(`/audit-events?${query}`, { token });
  }

  useEffect(() => {
    if (!token || !allowed) return;
    setLoading(true);
    fetchPage(0)
      .then((page) => {
        setEvents(page);
        setHasMore(page.length === PAGE_SIZE);
      })
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, allowed, entity]);

  async function loadMore() {
    const page = await fetchPage(events.length);
    setEvents((prev) => [...prev, ...page]);
    setHasMore(page.length === PAGE_SIZE);
  }

  if (!allowed) {
    return (
      <main className="page">
        <div className="empty-state">{t('common.ownerAdminOnly')}</div>
      </main>
    );
  }

  return (
    <main className="page">
      <h1 className="page-title">{t('nav.audit')}</h1>
      <p className="page-subtitle">{t('audit.subtitle')}</p>

      <div style={{ marginBottom: 16 }}>
        <select className="select" value={entity} onChange={(e) => setEntity(e.target.value)} style={{ maxWidth: 240 }} aria-label={t('audit.filter')}>
          <option value="">{t('audit.entity.all')}</option>
          {Object.entries(ENTITY_KEYS).map(([value, key]) => (
            <option key={value} value={value}>
              {t(key)}
            </option>
          ))}
        </select>
      </div>

      {loading ? (
        <p style={{ color: 'var(--color-text-muted)' }}>{t('common.loading')}</p>
      ) : events.length === 0 ? (
        <div className="empty-state">{t('audit.empty')}</div>
      ) : (
        <div className="card">
          {events.map((e, i) => (
            <div
              key={e.id}
              style={{
                display: 'grid',
                gridTemplateColumns: 'minmax(120px, 150px) minmax(0, 1fr)',
                gap: 12,
                padding: '12px 16px',
                borderTop: i ? '1px solid var(--color-border-subtle)' : 'none',
                fontSize: 13.5,
              }}
            >
              <span style={{ color: 'var(--color-text-subtle)', fontSize: 12, paddingTop: 1 }}>{formatDateTime(e.created_at)}</span>
              <span style={{ minWidth: 0 }}>
                <span className="badge" style={{ background: 'var(--color-bg)', color: 'var(--color-text-muted)', marginRight: 8 }}>
                  {e.entity_type === 'ticket' ? (
                    <Link href={`/tickets/${e.entity_id}?tab=history`}>{t('audit.entity.ticket')}</Link>
                  ) : (
                    t(ENTITY_KEYS[e.entity_type] ?? 'audit.entity.all')
                  )}
                </span>
                {describe(e)}
                <span style={{ color: 'var(--color-text-subtle)', fontSize: 12 }}> · {e.actor_email ?? t('audit.system')}</span>
              </span>
            </div>
          ))}
        </div>
      )}
      {hasMore && !loading && (
        <button className="btn btn-secondary" style={{ marginTop: 14 }} onClick={loadMore}>
          {t('audit.loadMore')}
        </button>
      )}
    </main>
  );
}

export default function AuditPage() {
  return (
    <RequireAuth>
      <AuditView />
    </RequireAuth>
  );
}
