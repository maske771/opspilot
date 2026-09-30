'use client';

import { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import { RequireAuth, useAuth } from '../../lib/auth';
import { apiFetch, ApiError, type DailyReport, type DailyReportSettings } from '../../lib/api';
import { useLocale } from '../../lib/locale';
import { isAdminRole, isManagerRole } from '../../lib/roles';
import { PRIORITY_KEYS, STATUS_KEYS, priorityBadgeStyle, statusBadgeStyle } from '../../lib/ui';

// Must match ALLOWED_TIMEZONES in apps/api/app/report_routes.py.
const ALLOWED_TIMEZONES = [
  'Asia/Bangkok',
  'Asia/Ho_Chi_Minh',
  'Asia/Singapore',
  'Asia/Jakarta',
  'Asia/Manila',
  'Asia/Hong_Kong',
  'Asia/Shanghai',
  'Asia/Tokyo',
  'Asia/Kolkata',
  'Asia/Dubai',
  'Europe/Moscow',
  'Europe/London',
  'Europe/Berlin',
  'UTC',
  'America/New_York',
  'America/Los_Angeles',
];

function DeliverySettings() {
  const { token } = useAuth();
  const { t } = useLocale();
  const [settings, setSettings] = useState<DailyReportSettings | null>(null);
  const [enabled, setEnabled] = useState(false);
  const [time, setTime] = useState('08:00');
  const [tz, setTz] = useState('Asia/Bangkok');
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!token) return;
    apiFetch<DailyReportSettings>('/reports/daily/settings', { token })
      .then((s) => {
        setSettings(s);
        setEnabled(s.daily_report_enabled);
        setTime(s.daily_report_time);
        setTz(s.daily_report_timezone);
      })
      .catch((err) => setError(err instanceof Error ? err.message : t('report.settingsLoadFailed')));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  async function save() {
    if (!token) return;
    setSaving(true);
    setSaved(false);
    setError(null);
    try {
      const updated = await apiFetch<DailyReportSettings>('/reports/daily/settings', {
        method: 'PATCH',
        token,
        body: { daily_report_enabled: enabled, daily_report_time: time, daily_report_timezone: tz },
      });
      setSettings(updated);
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t('report.settingsSaveFailed'));
    } finally {
      setSaving(false);
    }
  }

  if (!settings) return null;

  const dirty = enabled !== settings.daily_report_enabled || time !== settings.daily_report_time || tz !== settings.daily_report_timezone;

  return (
    <div className="card card-pad" style={{ marginBottom: 24 }}>
      <h2 style={{ fontSize: 15, marginTop: 0, marginBottom: 4 }}>{t('report.settingsTitle')}</h2>
      <p style={{ fontSize: 12.5, color: 'var(--color-text-subtle)', marginTop: 0, marginBottom: 16 }}>{t('report.settingsHint')}</p>

      {error && (
        <div style={{ padding: 12, borderRadius: 10, background: 'var(--color-danger-soft)', color: 'var(--color-danger)', marginBottom: 14, fontSize: 13 }}>
          {error}
        </div>
      )}

      <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13.5, marginBottom: 14, cursor: 'pointer' }}>
        <input type="checkbox" checked={enabled} onChange={(e) => setEnabled(e.target.checked)} />
        {t('report.settingsEnable')}
      </label>

      <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', alignItems: 'end', marginBottom: 16 }}>
        <div>
          <div style={{ fontSize: 12, color: 'var(--color-text-muted)', marginBottom: 6 }}>{t('report.settingsTime')}</div>
          <input type="time" value={time} onChange={(e) => setTime(e.target.value)} className="input" style={{ width: 130 }} disabled={!enabled} />
        </div>
        <div>
          <div style={{ fontSize: 12, color: 'var(--color-text-muted)', marginBottom: 6 }}>{t('report.settingsTimezone')}</div>
          <select value={tz} onChange={(e) => setTz(e.target.value)} className="select" style={{ minWidth: 200 }} disabled={!enabled}>
            {ALLOWED_TIMEZONES.map((zone) => (
              <option key={zone} value={zone}>
                {zone}
              </option>
            ))}
          </select>
        </div>
        <button type="button" className="btn btn-primary" onClick={save} disabled={saving || !dirty}>
          {t('report.settingsSave')}
        </button>
      </div>

      {saved && (
        <div style={{ padding: 10, borderRadius: 10, background: 'var(--status-completed-bg)', color: 'var(--status-completed-text)', fontSize: 13 }}>
          {t('report.settingsSaved')}
        </div>
      )}
    </div>
  );
}

function shiftDate(iso: string, days: number): string {
  const d = new Date(iso + 'T00:00:00Z');
  d.setUTCDate(d.getUTCDate() + days);
  return d.toISOString().slice(0, 10);
}

function todayIct(): string {
  // Matches the API's fixed Indochina Time (UTC+7) day boundary.
  const ict = new Date(Date.now() + 7 * 60 * 60 * 1000);
  return ict.toISOString().slice(0, 10);
}

function ReportView() {
  const { token, user } = useAuth();
  const { t, tOr, formatDate } = useLocale();
  const [date, setDate] = useState<string>(() => shiftDate(todayIct(), -1));
  const [report, setReport] = useState<DailyReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(() => {
    if (!token) return;
    setLoading(true);
    apiFetch<DailyReport>(`/reports/daily?date=${date}`, { token })
      .then(setReport)
      .catch((err) => setError(err instanceof Error ? err.message : t('report.loadFailed')))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, date]);

  useEffect(() => {
    load();
  }, [load]);

  if (!isManagerRole(user?.role)) {
    return (
      <main className="page">
        <div className="empty-state">{t('common.managersOnly')}</div>
      </main>
    );
  }

  const isToday = date >= todayIct();

  return (
    <main className="page">
      <h1 className="page-title">{t('nav.dailyReport')}</h1>
      <p className="page-subtitle">{t('report.subtitle')}</p>

      {isAdminRole(user?.role) && <DeliverySettings />}

      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 20 }}>
        <button type="button" className="btn btn-secondary" onClick={() => setDate((d) => shiftDate(d, -1))}>
          {t('report.prevDay')}
        </button>
        <input type="date" value={date} max={todayIct()} onChange={(e) => setDate(e.target.value)} className="input" style={{ width: 160 }} />
        <button type="button" className="btn btn-secondary" disabled={isToday} onClick={() => setDate((d) => shiftDate(d, 1))}>
          {t('report.nextDay')}
        </button>
      </div>

      {error && (
        <div style={{ padding: 14, borderRadius: 10, background: 'var(--color-danger-soft)', color: 'var(--color-danger)', marginBottom: 20 }}>
          {error}
        </div>
      )}

      {loading && !report ? (
        <p style={{ color: 'var(--color-text-muted)' }}>{t('common.loading')}</p>
      ) : report ? (
        <>
          <p style={{ fontSize: 13, color: 'var(--color-text-subtle)', marginBottom: 18 }}>
            {t('report.periodLabel', { date: formatDate(report.date) })}
          </p>

          <section style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 12, marginBottom: 28 }}>
            {[
              [t('report.created'), report.tickets_created],
              [t('report.closed'), report.tickets_closed],
              [t('report.currentlyOpen'), report.currently_open],
              [t('report.currentlyOverdue'), report.currently_overdue],
              [t('report.waitingApproval'), report.currently_waiting_approval],
            ].map(([label, value]) => (
              <div key={label as string} className="stat-tile">
                <div className="stat-tile-label">{label}</div>
                <div className="stat-tile-value">{value}</div>
              </div>
            ))}
          </section>

          <section style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 28 }}>
            <div className="card card-pad">
              <h2 style={{ fontSize: 15, marginTop: 0, marginBottom: 14 }}>{t('report.createdByPriority')}</h2>
              {report.tickets_created_by_priority.length === 0 ? (
                <p style={{ fontSize: 13, color: 'var(--color-text-subtle)', margin: 0 }}>{t('report.noneCreated')}</p>
              ) : (
                report.tickets_created_by_priority.map((row) => (
                  <div key={row.priority} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '7px 0' }}>
                    <span className="badge" style={priorityBadgeStyle(row.priority)}>
                      {t(PRIORITY_KEYS[row.priority])}
                    </span>
                    <span style={{ fontWeight: 700, fontSize: 14 }}>{row.count}</span>
                  </div>
                ))
              )}
            </div>
            <div className="card card-pad">
              <h2 style={{ fontSize: 15, marginTop: 0, marginBottom: 14 }}>{t('report.createdByCategory')}</h2>
              {report.tickets_created_by_category.length === 0 ? (
                <p style={{ fontSize: 13, color: 'var(--color-text-subtle)', margin: 0 }}>{t('report.noneCreated')}</p>
              ) : (
                report.tickets_created_by_category.map((row) => (
                  <div key={row.category} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '7px 0' }}>
                    <span style={{ fontSize: 13.5, color: 'var(--color-text-muted)' }}>{tOr(`category.${row.category}`, row.category)}</span>
                    <span style={{ fontWeight: 700, fontSize: 14 }}>{row.count}</span>
                  </div>
                ))
              )}
            </div>
          </section>

          <h2 style={{ fontSize: 15, marginBottom: 12 }}>{t('report.openCriticalHigh')}</h2>
          {report.open_critical_high.length === 0 ? (
            <div className="empty-state">{t('report.noOpenCriticalHigh')}</div>
          ) : (
            <div className="card">
              {report.open_critical_high.map((ticket) => (
                <Link key={ticket.id} href={`/tickets/${ticket.id}`} className="link-reset">
                  <div
                    className="list-row"
                    style={{ display: 'grid', gridTemplateColumns: '1.6fr 110px 130px 140px 110px', gap: 12, alignItems: 'center' }}
                  >
                    <div>
                      <div style={{ fontWeight: 600, fontSize: 14 }}>{ticket.title}</div>
                      <div style={{ fontSize: 12, color: 'var(--color-text-subtle)', marginTop: 3 }}>{tOr(`category.${ticket.category}`, ticket.category)}</div>
                    </div>
                    <span className="badge" style={priorityBadgeStyle(ticket.priority)}>
                      {t(PRIORITY_KEYS[ticket.priority])}
                    </span>
                    <span className="badge" style={statusBadgeStyle(ticket.status)}>
                      {t(STATUS_KEYS[ticket.status])}
                    </span>
                    <span style={{ fontSize: 12.5, color: 'var(--color-text-muted)' }}>
                      {ticket.assignee_email ? ticket.assignee_email.split('@')[0] : t('tickets.unassigned')}
                    </span>
                    <span style={{ fontSize: 12, color: ticket.overdue ? 'var(--color-danger)' : 'var(--color-text-muted)' }}>
                      {ticket.overdue ? t('tickets.overdueLabel') : ''}
                    </span>
                  </div>
                </Link>
              ))}
            </div>
          )}
        </>
      ) : null}
    </main>
  );
}

export default function DailyReportPage() {
  return (
    <RequireAuth>
      <ReportView />
    </RequireAuth>
  );
}
