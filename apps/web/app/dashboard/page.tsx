'use client';

import { useEffect, useState } from 'react';
import { Nav } from '../components/Nav';
import { RequireAuth, useAuth } from '../lib/auth';
import { apiFetch, type DashboardSummary } from '../lib/api';
import { PRIORITY_LABELS, STATUS_LABELS, priorityBadgeStyle } from '../lib/ui';

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
      <main className="page">
        <h1 className="page-title">Dashboard</h1>
        <p className="page-subtitle">Общая картина по всем обращениям и объектам.</p>

        {error && (
          <div style={{ padding: 14, borderRadius: 10, background: 'var(--color-danger-soft)', color: 'var(--color-danger)', marginBottom: 20 }}>
            {error}
          </div>
        )}

        {loading && !summary ? (
          <p style={{ color: 'var(--color-text-muted)' }}>Загрузка...</p>
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
                <div key={label as string} className="stat-tile">
                  <div className="stat-tile-label">{label}</div>
                  <div className="stat-tile-value">{value}</div>
                </div>
              ))}
            </section>

            <section style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
              <div className="card card-pad">
                <h2 style={{ fontSize: 15, marginTop: 0, marginBottom: 14 }}>По статусу</h2>
                {summary.tickets_by_status.map((row) => (
                  <div key={row.status} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '7px 0' }}>
                    <span style={{ fontSize: 13.5, color: 'var(--color-text-muted)' }}>{STATUS_LABELS[row.status] ?? row.status}</span>
                    <span style={{ fontWeight: 700, fontSize: 14 }}>{row.count}</span>
                  </div>
                ))}
              </div>
              <div className="card card-pad">
                <h2 style={{ fontSize: 15, marginTop: 0, marginBottom: 14 }}>По приоритету</h2>
                {summary.tickets_by_priority.map((row) => (
                  <div key={row.priority} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '7px 0' }}>
                    <span className="badge" style={priorityBadgeStyle(row.priority)}>
                      {PRIORITY_LABELS[row.priority] ?? row.priority}
                    </span>
                    <span style={{ fontWeight: 700, fontSize: 14 }}>{row.count}</span>
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

export default function DashboardPage() {
  return (
    <RequireAuth>
      <Dashboard />
    </RequireAuth>
  );
}
