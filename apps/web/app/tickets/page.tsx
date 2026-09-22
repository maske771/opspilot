'use client';

import { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import { Nav } from '../components/Nav';
import { RequireAuth, useAuth } from '../lib/auth';
import { apiFetch, type TicketPriority, type TicketRead, type TicketStatus, type UserRead } from '../lib/api';
import { PRIORITY_LABELS, STATUS_LABELS, priorityBadgeStyle, statusBadgeStyle } from '../lib/ui';

const NEXT_ACTION: Partial<Record<TicketStatus, { label: string; action: string }>> = {
  assigned: { label: 'Accept', action: 'accept' },
  accepted: { label: 'Start', action: 'start' },
  in_progress: { label: 'Complete', action: 'complete' },
  completed: { label: 'Close', action: 'close' },
};

function Badge({ text, style }: { text: string; style: React.CSSProperties }) {
  return (
    <span className="badge" style={style}>
      {text}
    </span>
  );
}

export function TicketsList({
  title = 'Tickets',
  defaultAssignee = '',
}: {
  title?: string;
  defaultAssignee?: 'me' | '';
}) {
  const { token, user } = useAuth();
  const [tickets, setTickets] = useState<TicketRead[]>([]);
  const [users, setUsers] = useState<UserRead[]>([]);
  const [statusFilter, setStatusFilter] = useState<TicketStatus | ''>('');
  const [priorityFilter, setPriorityFilter] = useState<TicketPriority | ''>('');
  const [assigneeFilter, setAssigneeFilter] = useState<'me' | 'unassigned' | ''>(defaultAssignee);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  const load = useCallback(() => {
    if (!token || !user) return;
    setLoading(true);
    setError(null);
    const params = new URLSearchParams();
    if (statusFilter) params.set('status', statusFilter);
    if (priorityFilter) params.set('priority', priorityFilter);
    if (assigneeFilter === 'me') params.set('assignee_id', user.id);
    if (assigneeFilter === 'unassigned') params.set('unassigned', 'true');
    Promise.all([
      apiFetch<TicketRead[]>(`/tickets?${params.toString()}`, { token }),
      apiFetch<UserRead[]>('/users', { token }),
    ])
      .then(([t, u]) => {
        setTickets(t);
        setUsers(u);
      })
      .catch((err) => setError(err instanceof Error ? err.message : 'Не удалось загрузить тикеты'))
      .finally(() => setLoading(false));
  }, [token, user, statusFilter, priorityFilter, assigneeFilter]);

  useEffect(() => {
    load();
  }, [load]);

  async function advance(ticket: TicketRead) {
    const next = NEXT_ACTION[ticket.status];
    if (!next || !token) return;
    setBusyId(ticket.id);
    try {
      await apiFetch(`/tickets/${ticket.id}/${next.action}`, { method: 'POST', token });
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Не удалось обновить тикет');
    } finally {
      setBusyId(null);
    }
  }

  function assigneeLabel(id: string | null) {
    if (!id) return 'Unassigned';
    const u = users.find((x) => x.id === id);
    return u ? u.email.split('@')[0] : 'Unknown';
  }

  return (
    <>
      <Nav />
      <main className="page">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
          <h1 className="page-title" style={{ marginBottom: 0 }}>{title}</h1>
          <button onClick={load} className="btn btn-secondary">
            Обновить
          </button>
        </div>
        <p className="page-subtitle">Все обращения, требующие внимания.</p>

        <div style={{ display: 'flex', gap: 10, marginBottom: 18 }}>
          <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value as TicketStatus | '')} className="select">
            <option value="">Все статусы</option>
            {Object.entries(STATUS_LABELS).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
          <select value={priorityFilter} onChange={(e) => setPriorityFilter(e.target.value as TicketPriority | '')} className="select">
            <option value="">Все приоритеты</option>
            {Object.entries(PRIORITY_LABELS).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
          <select
            value={assigneeFilter}
            onChange={(e) => setAssigneeFilter(e.target.value as 'me' | 'unassigned' | '')}
            className="select"
          >
            <option value="">Все исполнители</option>
            <option value="me">Назначено мне</option>
            <option value="unassigned">Без исполнителя</option>
          </select>
        </div>

        {error && (
          <div style={{ padding: 14, borderRadius: 10, background: 'var(--color-danger-soft)', color: 'var(--color-danger)', marginBottom: 20 }}>
            {error}
          </div>
        )}

        {loading ? (
          <p style={{ color: 'var(--color-text-muted)' }}>Загрузка...</p>
        ) : tickets.length === 0 ? (
          <div className="empty-state">Тикетов не найдено.</div>
        ) : (
          <div className="card">
            {tickets.map((ticket) => {
              const next = NEXT_ACTION[ticket.status];
              const overdue =
                ticket.status !== 'closed' &&
                ticket.resolution_deadline !== null &&
                new Date(ticket.resolution_deadline) < new Date();
              return (
                <div
                  key={ticket.id}
                  className="list-row"
                  style={{ display: 'grid', gridTemplateColumns: '1.6fr 110px 130px 120px 110px 110px', gap: 12, alignItems: 'center' }}
                >
                  <Link href={`/tickets/${ticket.id}`} className="link-reset">
                    <div style={{ fontWeight: 600, fontSize: 14 }}>{ticket.title}</div>
                    <div style={{ fontSize: 12, color: 'var(--color-text-subtle)', marginTop: 3 }}>{ticket.category}</div>
                  </Link>
                  <Badge text={PRIORITY_LABELS[ticket.priority]} style={priorityBadgeStyle(ticket.priority)} />
                  <Badge text={STATUS_LABELS[ticket.status]} style={statusBadgeStyle(ticket.status)} />
                  <div style={{ fontSize: 12.5, color: 'var(--color-text-muted)' }}>{assigneeLabel(ticket.assignee_id)}</div>
                  <div style={{ fontSize: 12, color: overdue ? 'var(--color-danger)' : 'var(--color-text-muted)' }}>
                    {overdue ? 'Просрочен' : ticket.resolution_deadline ? new Date(ticket.resolution_deadline).toLocaleDateString() : '—'}
                  </div>
                  <div>
                    {next && (
                      <button onClick={() => advance(ticket)} disabled={busyId === ticket.id} className="btn btn-secondary" style={{ padding: '6px 12px', fontSize: 12.5 }}>
                        {busyId === ticket.id ? '...' : next.label}
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </main>
    </>
  );
}

export default function TicketsPage() {
  return (
    <RequireAuth>
      <TicketsList />
    </RequireAuth>
  );
}
