'use client';

import { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import { Nav } from '../components/Nav';
import { RequireAuth, useAuth } from '../lib/auth';
import { apiFetch, type TicketPriority, type TicketRead, type TicketStatus } from '../lib/api';

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

const NEXT_ACTION: Partial<Record<TicketStatus, { label: string; action: string; next: TicketStatus }>> = {
  assigned: { label: 'Accept', action: 'accept', next: 'accepted' },
  accepted: { label: 'Start', action: 'start', next: 'in_progress' },
  in_progress: { label: 'Complete', action: 'complete', next: 'completed' },
  completed: { label: 'Close', action: 'close', next: 'closed' },
};

function Badge({ text, color }: { text: string; color: string }) {
  return (
    <span
      style={{
        display: 'inline-block',
        padding: '3px 9px',
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

function TicketsList() {
  const { token } = useAuth();
  const [tickets, setTickets] = useState<TicketRead[]>([]);
  const [statusFilter, setStatusFilter] = useState<TicketStatus | ''>('');
  const [priorityFilter, setPriorityFilter] = useState<TicketPriority | ''>('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  const load = useCallback(() => {
    if (!token) return;
    setLoading(true);
    setError(null);
    const params = new URLSearchParams();
    if (statusFilter) params.set('status', statusFilter);
    if (priorityFilter) params.set('priority', priorityFilter);
    apiFetch<TicketRead[]>(`/tickets?${params.toString()}`, { token })
      .then(setTickets)
      .catch((err) => setError(err instanceof Error ? err.message : 'Не удалось загрузить тикеты'))
      .finally(() => setLoading(false));
  }, [token, statusFilter, priorityFilter]);

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

  return (
    <>
      <Nav />
      <main style={{ maxWidth: 1080, margin: '0 auto', padding: 32 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
          <h1 style={{ fontSize: 26, margin: 0 }}>Tickets</h1>
          <button
            onClick={load}
            style={{ padding: '8px 14px', borderRadius: 8, border: '1px solid #d1d5db', background: '#fff', cursor: 'pointer' }}
          >
            Обновить
          </button>
        </div>

        <div style={{ display: 'flex', gap: 12, marginBottom: 18 }}>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value as TicketStatus | '')}
            style={select}
          >
            <option value="">Все статусы</option>
            {Object.entries(STATUS_LABELS).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
          <select
            value={priorityFilter}
            onChange={(e) => setPriorityFilter(e.target.value as TicketPriority | '')}
            style={select}
          >
            <option value="">Все приоритеты</option>
            {Object.entries(PRIORITY_LABELS).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </div>

        {error && (
          <div style={{ padding: 14, borderRadius: 10, background: '#fee2e2', color: '#991b1b', marginBottom: 20 }}>
            {error}
          </div>
        )}

        {loading ? (
          <p style={{ color: '#6b7280' }}>Загрузка...</p>
        ) : tickets.length === 0 ? (
          <div style={{ border: '1px dashed #d1d5db', borderRadius: 16, padding: 40, textAlign: 'center', color: '#6b7280' }}>
            Тикетов не найдено.
          </div>
        ) : (
          <div style={{ border: '1px solid #e5e7eb', borderRadius: 14, overflow: 'hidden', background: '#fff' }}>
            {tickets.map((ticket) => {
              const next = NEXT_ACTION[ticket.status];
              const overdue =
                ticket.status !== 'closed' &&
                ticket.resolution_deadline !== null &&
                new Date(ticket.resolution_deadline) < new Date();
              return (
                <div
                  key={ticket.id}
                  style={{
                    display: 'grid',
                    gridTemplateColumns: '1.6fr 130px 120px 140px 120px',
                    gap: 12,
                    alignItems: 'center',
                    padding: 16,
                    borderBottom: '1px solid #f0f0f0',
                  }}
                >
                  <Link href={`/tickets/${ticket.id}`} style={{ textDecoration: 'none', color: 'inherit' }}>
                    <div style={{ fontWeight: 600 }}>{ticket.title}</div>
                    <div style={{ fontSize: 12, color: '#9ca3af', marginTop: 4 }}>{ticket.category}</div>
                  </Link>
                  <Badge text={PRIORITY_LABELS[ticket.priority]} color={
                    ticket.priority === 'critical' ? '#991b1b'
                    : ticket.priority === 'high' ? '#b45309'
                    : ticket.priority === 'medium' ? '#1d4ed8'
                    : '#6b7280'
                  } />
                  <Badge text={STATUS_LABELS[ticket.status]} color={STATUS_COLORS[ticket.status]} />
                  <div style={{ fontSize: 12, color: overdue ? '#991b1b' : '#6b7280' }}>
                    {overdue ? 'Просрочен' : ticket.resolution_deadline ? new Date(ticket.resolution_deadline).toLocaleString() : '—'}
                  </div>
                  <div>
                    {next && (
                      <button
                        onClick={() => advance(ticket)}
                        disabled={busyId === ticket.id}
                        style={{
                          padding: '6px 12px',
                          borderRadius: 8,
                          border: '1px solid #d1d5db',
                          background: '#fff',
                          fontSize: 13,
                          cursor: 'pointer',
                        }}
                      >
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

const select: React.CSSProperties = {
  padding: '8px 12px',
  borderRadius: 8,
  border: '1px solid #d1d5db',
  fontSize: 14,
  background: '#fff',
};

export default function TicketsPage() {
  return (
    <RequireAuth>
      <TicketsList />
    </RequireAuth>
  );
}
