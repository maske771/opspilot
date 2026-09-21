'use client';

import { useCallback, useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { Nav } from '../../components/Nav';
import { RequireAuth, useAuth } from '../../lib/auth';
import {
  apiFetch,
  ApiError,
  type CustomerRead,
  type PropertyRead,
  type TicketPriority,
  type TicketRead,
  type TicketStatus,
  type UserRead,
} from '../../lib/api';

const STATUS_LABELS: Record<TicketStatus, string> = {
  new: 'New',
  assigned: 'Assigned',
  accepted: 'Accepted',
  in_progress: 'In progress',
  completed: 'Completed',
  waiting_approval: 'Waiting approval',
  closed: 'Closed',
};

const STATUS_COLORS: Record<TicketStatus, string> = {
  new: '#1d4ed8',
  assigned: '#7c3aed',
  accepted: '#0891b2',
  in_progress: '#b45309',
  completed: '#15803d',
  waiting_approval: '#a16207',
  closed: '#6b7280',
};

const PRIORITY_LABELS: Record<TicketPriority, string> = {
  critical: 'Critical',
  high: 'High',
  medium: 'Medium',
  low: 'Low',
};

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

function Badge({ text, color }: { text: string; color: string }) {
  return (
    <span
      style={{
        display: 'inline-block',
        padding: '3px 10px',
        borderRadius: 999,
        fontSize: 12,
        fontWeight: 700,
        color: '#fff',
        background: color,
      }}
    >
      {text}
    </span>
  );
}

function TicketDetail() {
  const { token } = useAuth();
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const ticketId = params.id;

  const [ticket, setTicket] = useState<TicketRead | null>(null);
  const [users, setUsers] = useState<UserRead[]>([]);
  const [properties, setProperties] = useState<PropertyRead[]>([]);
  const [customers, setCustomers] = useState<CustomerRead[]>([]);
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
      <main style={{ maxWidth: 860, margin: '0 auto', padding: 32 }}>
        <button
          onClick={() => router.push('/tickets')}
          style={{ border: 0, background: 'transparent', color: '#6b7280', fontSize: 13, cursor: 'pointer', padding: 0, marginBottom: 16 }}
        >
          ← Назад к тикетам
        </button>

        {error && (
          <div style={{ padding: 14, borderRadius: 10, background: '#fee2e2', color: '#991b1b', marginBottom: 20 }}>
            {error}
          </div>
        )}

        {loading || !ticket ? (
          <p style={{ color: '#6b7280' }}>Загрузка...</p>
        ) : (
          <>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 6 }}>
              <h1 style={{ fontSize: 24, margin: 0 }}>{ticket.title}</h1>
              <div style={{ display: 'flex', gap: 8 }}>
                <Badge
                  text={PRIORITY_LABELS[ticket.priority]}
                  color={
                    ticket.priority === 'critical'
                      ? '#991b1b'
                      : ticket.priority === 'high'
                        ? '#b45309'
                        : ticket.priority === 'medium'
                          ? '#1d4ed8'
                          : '#6b7280'
                  }
                />
                <Badge text={STATUS_LABELS[ticket.status]} color={STATUS_COLORS[ticket.status]} />
              </div>
            </div>
            <p style={{ color: '#6b7280', fontSize: 13, marginBottom: 20 }}>
              Создан {new Date(ticket.created_at).toLocaleString()}
              {customer && ` · ${customer.name}`}
              {property && ` · ${property.name}`}
            </p>

            {AVAILABLE_ACTIONS[ticket.status].length > 0 && (
              <div style={{ display: 'flex', gap: 8, marginBottom: 24 }}>
                {AVAILABLE_ACTIONS[ticket.status].map((a) => (
                  <button key={a.action} onClick={() => runAction(a.action)} disabled={busy} style={secondaryButton}>
                    {a.label}
                  </button>
                ))}
              </div>
            )}

            <form
              onSubmit={saveChanges}
              style={{
                display: 'flex',
                flexDirection: 'column',
                gap: 14,
                padding: 20,
                border: '1px solid #e5e7eb',
                borderRadius: 14,
                background: '#fff',
              }}
            >
              <label style={fieldLabel}>
                Заголовок
                <input value={title} onChange={(e) => setTitle(e.target.value)} style={input} required />
              </label>
              <label style={fieldLabel}>
                Описание
                <textarea
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  style={{ ...input, minHeight: 90, resize: 'vertical', fontFamily: 'inherit' }}
                  required
                />
              </label>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
                <label style={fieldLabel}>
                  Категория
                  <input value={category} onChange={(e) => setCategory(e.target.value)} style={input} />
                </label>
                <label style={fieldLabel}>
                  Приоритет
                  <select value={priority} onChange={(e) => setPriority(e.target.value as TicketPriority)} style={input}>
                    {Object.entries(PRIORITY_LABELS).map(([value, label]) => (
                      <option key={value} value={value}>
                        {label}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
              <label style={fieldLabel}>
                Исполнитель
                <select value={assigneeId} onChange={(e) => setAssigneeId(e.target.value)} style={input}>
                  <option value="">Не назначен</option>
                  {users.map((u) => (
                    <option key={u.id} value={u.id}>
                      {u.email} ({u.role})
                    </option>
                  ))}
                </select>
              </label>
              {assignee && (
                <p style={{ fontSize: 12, color: '#9ca3af', margin: 0 }}>Сейчас назначено: {assignee.email}</p>
              )}
              <button type="submit" disabled={busy} style={{ ...primaryButton, alignSelf: 'flex-start' }}>
                {busy ? 'Сохранение...' : 'Сохранить'}
              </button>
            </form>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14, marginTop: 20 }}>
              <div style={{ border: '1px solid #e5e7eb', borderRadius: 14, padding: 16, background: '#fff' }}>
                <div style={{ fontSize: 12, color: '#6b7280', marginBottom: 4 }}>Срок ответа</div>
                <div style={{ fontSize: 14 }}>
                  {ticket.response_deadline ? new Date(ticket.response_deadline).toLocaleString() : '—'}
                </div>
              </div>
              <div style={{ border: '1px solid #e5e7eb', borderRadius: 14, padding: 16, background: '#fff' }}>
                <div style={{ fontSize: 12, color: '#6b7280', marginBottom: 4 }}>Срок решения</div>
                <div style={{ fontSize: 14 }}>
                  {ticket.resolution_deadline ? new Date(ticket.resolution_deadline).toLocaleString() : '—'}
                </div>
              </div>
            </div>
          </>
        )}
      </main>
    </>
  );
}

const fieldLabel: React.CSSProperties = { display: 'flex', flexDirection: 'column', gap: 6, fontSize: 13, color: '#374151' };
const input: React.CSSProperties = { padding: '9px 12px', borderRadius: 8, border: '1px solid #d1d5db', fontSize: 14 };
const primaryButton: React.CSSProperties = {
  padding: '10px 18px',
  borderRadius: 8,
  border: 0,
  background: '#111827',
  color: '#fff',
  fontSize: 14,
  cursor: 'pointer',
};
const secondaryButton: React.CSSProperties = {
  padding: '8px 14px',
  borderRadius: 8,
  border: '1px solid #d1d5db',
  background: '#fff',
  fontSize: 13,
  cursor: 'pointer',
};

export default function TicketDetailPage() {
  return (
    <RequireAuth>
      <TicketDetail />
    </RequireAuth>
  );
}
