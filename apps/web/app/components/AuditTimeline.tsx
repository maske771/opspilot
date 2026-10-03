'use client';

import type { AuditEventRead } from '../lib/api';
import { useLocale } from '../lib/locale';

export function AuditTimeline({ events, describe }: { events: AuditEventRead[]; describe: (e: AuditEventRead) => string }) {
  const { t, formatDateTime } = useLocale();
  if (events.length === 0) {
    return <p style={{ fontSize: 13, color: 'var(--color-text-subtle)', margin: 0 }}>{t('audit.empty')}</p>;
  }
  return (
    <ol style={{ listStyle: 'none', margin: 0, padding: 0, display: 'flex', flexDirection: 'column', gap: 12 }}>
      {events.map((e) => (
        <li key={e.id} style={{ display: 'flex', gap: 12, fontSize: 13.5 }}>
          <span style={{ color: 'var(--color-text-subtle)', fontSize: 12, minWidth: 130, paddingTop: 1 }}>{formatDateTime(e.created_at)}</span>
          <span>
            <span>{describe(e)}</span>
            <span style={{ color: 'var(--color-text-subtle)', fontSize: 12 }}> · {e.actor_email?.split('@')[0] ?? t('audit.system')}</span>
          </span>
        </li>
      ))}
    </ol>
  );
}
