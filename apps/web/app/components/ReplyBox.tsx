'use client';

import { useState } from 'react';
import { useAuth } from '../lib/auth';
import { apiFetch, ApiError, type MessageRead } from '../lib/api';

export function ReplyBox({
  conversationId,
  onSent,
}: {
  conversationId: string;
  onSent: (message: MessageRead) => void;
}) {
  const { token } = useAuth();
  const [text, setText] = useState('');
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function send(e: React.FormEvent) {
    e.preventDefault();
    if (!token || !text.trim()) return;
    setSending(true);
    setError(null);
    try {
      const result = await apiFetch<{ message: MessageRead; delivered: boolean }>(
        `/conversations/${conversationId}/messages`,
        { method: 'POST', token, body: { content: text.trim() } },
      );
      onSent(result.message);
      setText('');
      if (!result.delivered) {
        setError('Сообщение сохранено, но не удалось доставить через канал — проверьте, подключены ли креды канала.');
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось отправить сообщение');
    } finally {
      setSending(false);
    }
  }

  return (
    <div style={{ marginTop: 12 }}>
      <form onSubmit={send} style={{ display: 'flex', gap: 8 }}>
        <input
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Написать клиенту..."
          className="input"
          style={{ flex: 1 }}
        />
        <button type="submit" disabled={sending || !text.trim()} className="btn btn-accent">
          {sending ? '...' : 'Отправить'}
        </button>
      </form>
      {error && <div style={{ fontSize: 12, color: 'var(--color-danger)', marginTop: 6 }}>{error}</div>}
    </div>
  );
}
