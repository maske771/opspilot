'use client';

import { useCallback, useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { Nav } from '../../components/Nav';
import { MessageTimeline } from '../../components/MessageTimeline';
import { ReplyBox } from '../../components/ReplyBox';
import { RequireAuth, useAuth } from '../../lib/auth';
import {
  apiFetch,
  ApiError,
  type CustomerRead,
  type MessageRead,
  type PropertyRead,
  type TicketPriority,
  type TicketRead,
  type TicketStatus,
  type UserRead,
} from '../../lib/api';
import { PRIORITY_LABELS, STATUS_LABELS, priorityBadgeStyle, statusBadgeStyle } from '../../lib/ui';

const AVAILABLE_ACTIONS: Record<TicketStatus, { action: string; label: string }[]> = {
  new: [
    { action: 'start', label: 'Start' },
    { action: 'close', label: 'Close' },
  ],
  assigned: [
    { action: 'accept', label: 'Accept' },
    { action: 'start', label: 'Start' },
    { action: 'close', label: 'Close' },
  ],
  accepted: [
    { action: 'start', label: 'Start' },
    { action: 'close', label: 'Close' },
  ],
  in_progress: [
    { action: 'complete', label: 'Complete' },
    { action: 'close', label: 'Close' },
  ],
  completed: [{ action: 'close', label: 'Close' }],
  waiting_approval: [
    { action: 'start', label: 'Resume' },
    { action: 'close', label: 'Close' },
  ],
  closed: [],
};

function TicketDetail() {
  const { token } = useAuth();
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const ticketId = params.id;

  const [ticket, setTicket] = useState<TicketRead | null>(null);
  const [users, setUsers] = useState<UserRead[]>([]);
  const [properties, setProperties] = useState<PropertyRead[]>([]);
  const [customers, setCustomers] = useState<CustomerRead[]>([]);
  const [messages, setMessages] = useState<MessageRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [category, setCategory] = useState('');
  const [priority, setPriority] = useState<TicketPriority>('medium');
  const [assigneeId, setAssigneeId] = useState('');

  const load = useCallback(() => {
    if (!token) return;
    setLoading(true);
    setError(null);
    Promise.all([
      apiFetch<TicketRead>(`/tickets/${ticketId}`, { token }),
      apiFetch<UserRead[]>('/users', { token }),
      apiFetch<PropertyRead[]>('/properties', { token }),
      apiFetch<CustomerRead[]>('/customers', { token }),
    ])
      .then(([t, u, p, c]) => {
        setTicket(t);
        setUsers(u);
        setProperties(p);
        setCustomers(c);
        setTitle(t.title);
        setDescription(t.description);
        setCategory(t.category);
        setPriority(t.priority);
        setAssigneeId(t.assignee_id ?? '');
        if (t.conversation_id) {
          apiFetch<MessageRead[]>(`/conversations/${t.conversation_id}/messages`, { token }).then(setMessages);
        }
      })
      .catch((err) => setError(err instanceof Error ? err.message : 'Не удалось загрузить тикет'))
      .finally(() => setLoading(false));
  }, [token, ticketId]);

  useEffect(() => {
    load();
  }, [load]);

  async function saveChanges(e: React.FormEvent) {
    e.preventDefault();
    if (!token || !ticket) return;
    setBusy(true);
    setError(null);
    try {
      const updated = await apiFetch<TicketRead>(`/tickets/${ticket.id}`, {
        method: 'PATCH',
        token,
        body: {
          title,
          description,
          category,
          priority,
          assignee_id: assigneeId || null,
        },
      });
      setTicket(updated);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось сохранить изменения');
    } finally {
      setBusy(false);
    }
  }

  async function runAction(action: string) {
    if (!token || !ticket) return;
    setBusy(true);
    setError(null);
    try {
      const updated = await apiFetch<TicketRead>(`/tickets/${ticket.id}/${action}`, { method: 'POST', token });
      setTicket(updated);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось выполнить действие');
    } finally {
      setBusy(false);
    }
  }

  const property = properties.find((p) => p.id === ticket?.property_id);
  const customer = customers.find((c) => c.id === ticket?.customer_id);
  const assignee = users.find((u) => u.id === ticket?.assignee_id);

  return (
    <>
      <Nav />
      <main className="page-narrow">
        <button onClick={() => router.push('/tickets')} className="btn btn-ghost" style={{ marginBottom: 16, marginLeft: -8 }}>
          ← Назад к тикетам
        </button>

        {error && (
          <div style={{ padding: 14, borderRadius: 10, background: 'var(--color-danger-soft)', color: 'var(--color-danger)', marginBottom: 20 }}>
            {error}
          </div>
        )}

        {loading || !ticket ? (
          <p style={{ color: 'var(--color-text-muted)' }}>Загрузка...</p>
        ) : (
          <>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 6 }}>
              <h1 style={{ fontSize: 22, fontWeight: 700, letterSpacing: '-0.01em', margin: 0 }}>{ticket.title}</h1>
              <div style={{ display: 'flex', gap: 8, flexShrink: 0 }}>
                <span className="badge" style={priorityBadgeStyle(ticket.priority)}>
                  {PRIORITY_LABELS[ticket.priority]}
                </span>
                <span className="badge" style={statusBadgeStyle(ticket.status)}>
                  {STATUS_LABELS[ticket.status]}
                </span>
              </div>
            </div>
            <p style={{ color: 'var(--color-text-muted)', fontSize: 13, marginBottom: 20 }}>
              Создан {new Date(ticket.created_at).toLocaleString()}
              {customer && ` · ${customer.name}`}
              {property && ` · ${property.name}`}
            </p>

            {AVAILABLE_ACTIONS[ticket.status].length > 0 && (
              <div style={{ display: 'flex', gap: 8, marginBottom: 24 }}>
                {AVAILABLE_ACTIONS[ticket.status].map((a) => (
                  <button key={a.action} onClick={() => runAction(a.action)} disabled={busy} className="btn btn-secondary">
                    {a.label}
                  </button>
                ))}
              </div>
            )}

            <form onSubmit={saveChanges} className="card card-pad" style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              <label className="field">
                Заголовок
                <input value={title} onChange={(e) => setTitle(e.target.value)} className="input" required />
              </label>
              <label className="field">
                Описание
                <textarea value={description} onChange={(e) => setDescription(e.target.value)} className="textarea" required />
              </label>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
                <label className="field">
                  Категория
                  <input value={category} onChange={(e) => setCategory(e.target.value)} className="input" />
                </label>
                <label className="field">
                  Приоритет
                  <select value={priority} onChange={(e) => setPriority(e.target.value as TicketPriority)} className="select">
                    {Object.entries(PRIORITY_LABELS).map(([value, label]) => (
                      <option key={value} value={value}>
                        {label}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
              <label className="field">
                Исполнитель
                <select value={assigneeId} onChange={(e) => setAssigneeId(e.target.value)} className="select">
                  <option value="">Не назначен</option>
                  {users.map((u) => (
                    <option key={u.id} value={u.id}>
                      {u.email} ({u.role})
                    </option>
                  ))}
                </select>
              </label>
              {assignee && (
                <p style={{ fontSize: 12, color: 'var(--color-text-subtle)', margin: 0 }}>Сейчас назначено: {assignee.email}</p>
              )}
              <button type="submit" disabled={busy} className="btn btn-accent" style={{ alignSelf: 'flex-start' }}>
                {busy ? 'Сохранение...' : 'Сохранить'}
              </button>
            </form>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14, marginTop: 20 }}>
              <div className="stat-tile">
                <div className="stat-tile-label">Срок ответа</div>
                <div style={{ fontSize: 14, fontWeight: 600 }}>
                  {ticket.response_deadline ? new Date(ticket.response_deadline).toLocaleString() : '—'}
                </div>
              </div>
              <div className="stat-tile">
                <div className="stat-tile-label">Срок решения</div>
                <div style={{ fontSize: 14, fontWeight: 600 }}>
                  {ticket.resolution_deadline ? new Date(ticket.resolution_deadline).toLocaleString() : '—'}
                </div>
              </div>
            </div>

            {ticket.conversation_id && (
              <div style={{ marginTop: 24 }}>
                <h2 style={{ fontSize: 15, marginBottom: 12 }}>Переписка</h2>
                <MessageTimeline messages={messages} />
                <ReplyBox
                  conversationId={ticket.conversation_id}
                  onSent={(message) => setMessages((prev) => [...prev, message])}
                />
              </div>
            )}
          </>
        )}
      </main>
    </>
  );
}

export default function TicketDetailPage() {
  return (
    <RequireAuth>
      <TicketDetail />
    </RequireAuth>
  );
}
