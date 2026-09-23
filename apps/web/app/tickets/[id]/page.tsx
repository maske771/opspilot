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
import type { MessageKey } from '../../lib/i18n/en';
import { useLocale } from '../../lib/locale';
import { PRIORITY_KEYS, STATUS_KEYS, priorityBadgeStyle, statusBadgeStyle } from '../../lib/ui';

const AVAILABLE_ACTIONS: Record<TicketStatus, { action: string; label: MessageKey }[]> = {
  new: [
    { action: 'start', label: 'action.start' },
    { action: 'close', label: 'action.close' },
  ],
  assigned: [
    { action: 'accept', label: 'action.accept' },
    { action: 'start', label: 'action.start' },
    { action: 'close', label: 'action.close' },
  ],
  accepted: [
    { action: 'start', label: 'action.start' },
    { action: 'close', label: 'action.close' },
  ],
  in_progress: [
    { action: 'complete', label: 'action.complete' },
    { action: 'close', label: 'action.close' },
  ],
  completed: [{ action: 'close', label: 'action.close' }],
  waiting_approval: [
    { action: 'start', label: 'action.resume' },
    { action: 'close', label: 'action.close' },
  ],
  closed: [],
};

function TicketDetail() {
  const { token } = useAuth();
  const { t, tOr, formatDateTime } = useLocale();
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
      .then(([tk, u, p, c]) => {
        setTicket(tk);
        setUsers(u);
        setProperties(p);
        setCustomers(c);
        setTitle(tk.title);
        setDescription(tk.description);
        setCategory(tk.category);
        setPriority(tk.priority);
        setAssigneeId(tk.assignee_id ?? '');
        if (tk.conversation_id) {
          apiFetch<MessageRead[]>(`/conversations/${tk.conversation_id}/messages`, { token }).then(setMessages);
        }
      })
      .catch((err) => setError(err instanceof Error ? err.message : t('ticket.loadFailed')))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
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
      setError(err instanceof ApiError ? err.message : t('ticket.saveFailed'));
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
      setError(err instanceof ApiError ? err.message : t('ticket.actionFailed'));
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
          {t('ticket.back')}
        </button>

        {error && (
          <div style={{ padding: 14, borderRadius: 10, background: 'var(--color-danger-soft)', color: 'var(--color-danger)', marginBottom: 20 }}>
            {error}
          </div>
        )}

        {loading || !ticket ? (
          <p style={{ color: 'var(--color-text-muted)' }}>{t('common.loading')}</p>
        ) : (
          <>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 6 }}>
              <h1 style={{ fontSize: 22, fontWeight: 700, letterSpacing: '-0.01em', margin: 0 }}>{ticket.title}</h1>
              <div style={{ display: 'flex', gap: 8, flexShrink: 0 }}>
                <span className="badge" style={priorityBadgeStyle(ticket.priority)}>
                  {t(PRIORITY_KEYS[ticket.priority])}
                </span>
                <span className="badge" style={statusBadgeStyle(ticket.status)}>
                  {t(STATUS_KEYS[ticket.status])}
                </span>
              </div>
            </div>
            <p style={{ color: 'var(--color-text-muted)', fontSize: 13, marginBottom: 20 }}>
              {t('ticket.created', { date: formatDateTime(ticket.created_at) })}
              {customer && ` · ${customer.name}`}
              {property && ` · ${property.name}`}
            </p>

            {AVAILABLE_ACTIONS[ticket.status].length > 0 && (
              <div style={{ display: 'flex', gap: 8, marginBottom: 24 }}>
                {AVAILABLE_ACTIONS[ticket.status].map((a) => (
                  <button key={a.action} onClick={() => runAction(a.action)} disabled={busy} className="btn btn-secondary">
                    {t(a.label)}
                  </button>
                ))}
              </div>
            )}

            <form onSubmit={saveChanges} className="card card-pad" style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              <label className="field">
                {t('ticket.title')}
                <input value={title} onChange={(e) => setTitle(e.target.value)} className="input" required />
              </label>
              <label className="field">
                {t('ticket.description')}
                <textarea value={description} onChange={(e) => setDescription(e.target.value)} className="textarea" required />
              </label>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
                <label className="field">
                  {t('ticket.category')}
                  <input value={category} onChange={(e) => setCategory(e.target.value)} className="input" />
                </label>
                <label className="field">
                  {t('ticket.priority')}
                  <select value={priority} onChange={(e) => setPriority(e.target.value as TicketPriority)} className="select">
                    {Object.entries(PRIORITY_KEYS).map(([value, key]) => (
                      <option key={value} value={value}>
                        {t(key)}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
              <label className="field">
                {t('ticket.assignee')}
                <select value={assigneeId} onChange={(e) => setAssigneeId(e.target.value)} className="select">
                  <option value="">{t('ticket.notAssigned')}</option>
                  {users.map((u) => (
                    <option key={u.id} value={u.id}>
                      {u.email} ({tOr(`role.${u.role}`, u.role)})
                    </option>
                  ))}
                </select>
              </label>
              {assignee && (
                <p style={{ fontSize: 12, color: 'var(--color-text-subtle)', margin: 0 }}>
                  {t('ticket.currentlyAssigned', { email: assignee.email })}
                </p>
              )}
              <button type="submit" disabled={busy} className="btn btn-accent" style={{ alignSelf: 'flex-start' }}>
                {busy ? t('common.saving') : t('common.save')}
              </button>
            </form>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14, marginTop: 20 }}>
              <div className="stat-tile">
                <div className="stat-tile-label">{t('ticket.responseDue')}</div>
                <div style={{ fontSize: 14, fontWeight: 600 }}>
                  {ticket.response_deadline ? formatDateTime(ticket.response_deadline) : '—'}
                </div>
              </div>
              <div className="stat-tile">
                <div className="stat-tile-label">{t('ticket.resolutionDue')}</div>
                <div style={{ fontSize: 14, fontWeight: 600 }}>
                  {ticket.resolution_deadline ? formatDateTime(ticket.resolution_deadline) : '—'}
                </div>
              </div>
            </div>

            {ticket.conversation_id && (
              <div style={{ marginTop: 24 }}>
                <h2 style={{ fontSize: 15, marginBottom: 12 }}>{t('ticket.conversation')}</h2>
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
