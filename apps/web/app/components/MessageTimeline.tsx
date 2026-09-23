'use client';

import type { MessageRead } from '../lib/api';
import { useLocale } from '../lib/locale';
import { AttachmentImage } from './AttachmentImage';

export function MessageTimeline({ messages }: { messages: MessageRead[] }) {
  const { t, formatDateTime } = useLocale();

  if (messages.length === 0) {
    return <p style={{ fontSize: 13, color: 'var(--color-text-subtle)' }}>{t('timeline.empty')}</p>;
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      {messages.map((m) => (
        <div
          key={m.id}
          style={{
            alignSelf: m.direction === 'outbound' ? 'flex-end' : 'flex-start',
            maxWidth: '72%',
          }}
        >
          {m.attachments.length > 0 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginBottom: m.content ? 6 : 0 }}>
              {m.attachments.map((a) => (
                <AttachmentImage key={a.id} id={a.id} />
              ))}
            </div>
          )}
          {m.content && (
            <div
              style={{
                padding: '10px 14px',
                borderRadius: 14,
                background: m.direction === 'outbound' ? 'var(--color-accent)' : 'var(--color-surface)',
                color: m.direction === 'outbound' ? '#fff' : 'var(--color-text)',
                border: m.direction === 'outbound' ? 'none' : '1px solid var(--color-border)',
                boxShadow: 'var(--shadow-sm)',
              }}
            >
              <div style={{ fontSize: 14, whiteSpace: 'pre-wrap', lineHeight: 1.45 }}>{m.content}</div>
            </div>
          )}
          <div
            style={{
              fontSize: 11,
              marginTop: 4,
              color: 'var(--color-text-subtle)',
              textAlign: m.direction === 'outbound' ? 'right' : 'left',
            }}
          >
            {formatDateTime(m.created_at)}
          </div>
        </div>
      ))}
    </div>
  );
}
