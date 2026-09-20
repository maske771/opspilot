'use client';

import { useEffect, useState } from 'react';
import { Nav } from './components/Nav';
import { RequireAuth, useAuth } from './lib/auth';
import { apiFetch, type DashboardSummary } from './lib/api';

const STATUS_LABELS: Record<string, string> = {
  new: 'New',
  assigned: 'Assigned',
  accepted: 'Accepted',
  in_progress: 'In progress',
  completed: 'Completed',
  waiting_approval: 'Waiting approval',
  closed: 'Closed',
};

const PRIORITY_LABELS: Record<string, string> = {
  critical: 'Critical',
  high: 'High',
  medium: 'Medium',
  low: 'Low',
};

const PRIORITY_COLORS: Record<string, string> = {
  critical: '#991b1b',
  high: '#b45309',
  medium: '#1d4ed8',
  low: '#6b7280',
};

function Dashboard() {
  const { token } = useAuth();
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!token) return;
    setLoading(true);
    apiFetch<DashboardSummary>('/dashboard/summary', { token })
      .then(setSummary)
      .catch((err) => setError(err instanceof Error ? err.message : 'Не удалось загрузить сводку'))
      .finally(() => setLoading(false));
  }, [token]);

  return (
    <>
      <Nav />
      <main style={{ maxWidth: 1080, margin: '0 auto', padding: 32 }}>
        <h1 style={{ fontSize: 26, marginBottom: 24 }}>Dashboard</h1>

        {error && (
          <div style={{ padding: 14, borderRadius: 10, background: '#fee2e2', color: '#991b1b', marginBottom: 20 }}>
            {error}
          </div>
        )}

        {loading && !summary ? (
          <p style={{ color: '#6b7280' }}>Загрузка...</p>
        ) : summary ? (
          <>
            <section
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))',
                gap: 12,
                marginBottom: 28,
              }}
            >
              {[
                ['Всего тикетов', summary.tickets_total],
                ['Открыто', summary.tickets_open],
                ['Просрочено', summary.tickets_overdue],
                ['Клиенты', summary.customers_total],
                ['Объекты', summary.properties_total],
                ['Юниты', summary.units_total],
              ].map(([label, value]) => (
                <div
                  key={label as string}
                  style={{ border: '1px solid #e5e7eb', borderRadius: 14, padding: 18, background: '#fff' }}
                >
                  <div style={{ fontSize: 12, color: '#6b7280' }}>{label}</div>
                  <div style={{ fontSize: 26, fontWeight: 800, marginTop: 8 }}>{value}</div>
                </div>
              ))}
            </section>

            <section style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
              <div style={{ border: '1px solid #e5e7eb', borderRadius: 14, padding: 20, background: '#fff' }}>
                <h2 style={{ fontSize: 15, marginTop: 0, marginBottom: 14 }}>По статусу</h2>
                {summary.tickets_by_status.map((row) => (
                  <div
                    key={row.status}
                    style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 0', fontSize: 14 }}
                  >
                    <span style={{ color: '#374151' }}>{STATUS_LABELS[row.status] ?? row.status}</span>
                    <span style={{ fontWeight: 700 }}>{row.count}</span>
                  </div>
                ))}
              </div>
              <div style={{ border: '1px solid #e5e7eb', borderRadius: 14, padding: 20, background: '#fff' }}>
                <h2 style={{ fontSize: 15, marginTop: 0, marginBottom: 14 }}>По приоритету</h2>
                {summary.tickets_by_priority.map((row) => (
                  <div
                    key={row.priority}
                    style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 0', fontSize: 14 }}
                  >
                    <span style={{ color: PRIORITY_COLORS[row.priority] ?? '#374151' }}>
                      {PRIORITY_LABELS[row.priority] ?? row.priority}
                    </span>
                    <span style={{ fontWeight: 700 }}>{row.count}</span>
                  </div>
                ))}
              </div>
            </section>
          </>
        ) : null}
      </main>
    </>
  );
}

export default function Home() {
  return (
    <RequireAuth>
      <Dashboard />
    </RequireAuth>
  );
}
