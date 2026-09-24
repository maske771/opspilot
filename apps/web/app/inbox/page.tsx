'use client';

import { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import { MessageTimeline } from '../components/MessageTimeline';
import { ReplyBox } from '../components/ReplyBox';
import { RequireAuth, useAuth } from '../lib/auth';
import { apiFetch, type InboxItem, type MessageRead } from '../lib/api';
import { useLocale } from '../lib/locale';
import { PRIORITY_KEYS, STATUS_KEYS, priorityBadgeStyle, statusBadgeStyle } from '../lib/ui';

const CHANNEL_LABELS: Record<string, string> = {
  line: 'LINE',
  telegram: 'Telegram',
  whatsapp: 'WhatsApp',
  email: 'Email',
};

export function InboxView() {
  const { token } = useAuth();
  const { t, timeAgo } = useLocale();
  const [items, setItems] = useState<InboxItem[]>([]);
  const [selected, setSelected] = useState<InboxItem | null>(null);
  const [messages, setMessages] = useState<MessageRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadingThread, setLoadingThread] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    if (!token) return;
    setLoading(true);
    apiFetch<InboxItem[]>('/inbox', { token })
      .then((data) => {
        setItems(data);
        if (!selected && data.length > 0) setSelected(data[0]);
      })
      .catch((err) => setError(err instanceof Error ? err.message : t('inbox.loadFailed')))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (!token || !selected) return;
    setLoadingThread(true);
    apiFetch<MessageRead[]>(`/conversations/${selected.conversation_id}/messages`, { token })
      .then(setMessages)
      .catch(() => setMessages([]))
      .finally(() => setLoadingThread(false));
  }, [token, selected]);

  return (
    <>
      <main className="page" style={{ maxWidth: 1180 }}>
        <h1 className="page-title">{t('nav.inbox')}</h1>
        <p className="page-subtitle">{t('inbox.subtitle')}</p>

        {error && (
          <div style={{ padding: 14, borderRadius: 10, background: 'var(--color-danger-soft)', color: 'var(--color-danger)', marginBottom: 20 }}>
            {error}
          </div>
        )}

        {loading ? (
          <p style={{ color: 'var(--color-text-muted)' }}>{t('common.loading')}</p>
        ) : items.length === 0 ? (
          <div className="empty-state">{t('inbox.empty')}</div>
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: '360px 1fr', gap: 16, alignItems: 'start' }}>
            <div className="card" style={{ maxHeight: 640, overflowY: 'auto' }}>
              {items.map((item) => {
                const active = selected?.conversation_id === item.conversation_id;
                return (
                  <button
                    key={item.conversation_id}
                    onClick={() => setSelected(item)}
                    className="list-row"
                    style={{
                      display: 'block',
                      width: '100%',
                      textAlign: 'left',
                      border: 0,
                      cursor: 'pointer',
                      color: 'inherit',
                      background: active ? 'var(--color-accent-soft)' : 'transparent',
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 4 }}>
                      <span style={{ fontWeight: 600, fontSize: 14 }}>{item.customer?.name ?? t('inbox.noName')}</span>
                      <span style={{ fontSize: 11, color: 'var(--color-text-subtle)' }}>{timeAgo(item.updated_at)}</span>
                    </div>
                    <div style={{ fontSize: 12.5, color: 'var(--color-text-muted)', marginBottom: 6, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {item.last_message ? item.last_message.content : t('inbox.noMessages')}
                    </div>
                    <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                      <span className="badge" style={{ background: 'var(--color-bg)', color: 'var(--color-text-muted)' }}>
                        {CHANNEL_LABELS[item.channel.type] ?? item.channel.type}
                      </span>
                      {item.ticket && (
                        <span className="badge" style={statusBadgeStyle(item.ticket.status)}>
                          {t(STATUS_KEYS[item.ticket.status])}
                        </span>
                      )}
                    </div>
                  </button>
                );
              })}
            </div>

            <div className="card card-pad" style={{ minHeight: 480, display: 'flex', flexDirection: 'column' }}>
              {!selected ? (
                <p style={{ color: 'var(--color-text-muted)' }}>{t('inbox.selectConversation')}</p>
              ) : (
                <>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 16 }}>
                    <div>
                      <h2 style={{ fontSize: 17, margin: 0 }}>{selected.customer?.name ?? t('inbox.noName')}</h2>
                      <p style={{ fontSize: 12.5, color: 'var(--color-text-muted)', margin: '4px 0 0' }}>
                        {CHANNEL_LABELS[selected.channel.type] ?? selected.channel.type} · {selected.channel.name}
                      </p>
                    </div>
                    {selected.ticket && (
                      <Link href={`/tickets/${selected.ticket.id}`} className="btn btn-secondary" style={{ textDecoration: 'none' }}>
                        {t('inbox.openTicket')}
                      </Link>
                    )}
                  </div>

                  {selected.ticket && (
                    <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
                      <span className="badge" style={priorityBadgeStyle(selected.ticket.priority)}>
                        {t(PRIORITY_KEYS[selected.ticket.priority])}
                      </span>
                      <span className="badge" style={statusBadgeStyle(selected.ticket.status)}>
                        {t(STATUS_KEYS[selected.ticket.status])}
                      </span>
                    </div>
                  )}

                  <div style={{ flex: 1, overflowY: 'auto' }}>
                    {loadingThread ? (
                      <p style={{ color: 'var(--color-text-muted)' }}>{t('inbox.loadingThread')}</p>
                    ) : (
                      <MessageTimeline messages={messages} />
                    )}
                  </div>

                  <ReplyBox
                    conversationId={selected.conversation_id}
                    onSent={(message) => setMessages((prev) => [...prev, message])}
                  />
                </>
              )}
            </div>
          </div>
        )}
      </main>
    </>
  );
}

export default function InboxPage() {
  return (
    <RequireAuth>
      <InboxView />
    </RequireAuth>
  );
}
