import type { MessageRead } from '../lib/api';

export function MessageTimeline({ messages }: { messages: MessageRead[] }) {
  if (messages.length === 0) {
    return <p style={{ fontSize: 13, color: 'var(--color-text-subtle)' }}>Сообщений пока нет.</p>;
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
          <div
            style={{
              fontSize: 11,
              marginTop: 4,
              color: 'var(--color-text-subtle)',
              textAlign: m.direction === 'outbound' ? 'right' : 'left',
            }}
          >
            {new Date(m.created_at).toLocaleString()}
          </div>
        </div>
      ))}
    </div>
  );
}
