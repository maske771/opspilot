'use client';

import { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import { RequireAuth, useAuth } from '../../lib/auth';
import { apiFetch, ApiError, type DailyReport, type DailyReportSettings } from '../../lib/api';
import { LOCALES, useLocale } from '../../lib/locale';
import { useServices } from '../../lib/services';
import { isAdminRole, isManagerRole } from '../../lib/roles';
import { PRIORITY_KEYS, STATUS_KEYS, priorityBadgeStyle, statusBadgeStyle } from '../../lib/ui';

const PREVIEW_VALUES = {
  date: '2026-01-01',
  created: 5,
  closed: 3,
  open: 7,
  overdue: 1,
  waiting: 2,
  critical: 1,
  url: 'https://app.example.com/reports/daily?date=2026-01-01',
};

function renderPreview(template: string): string {
  return template.replace(/\{(\w+)\}/g, (match, key) => (key in PREVIEW_VALUES ? String(PREVIEW_VALUES[key as keyof typeof PREVIEW_VALUES]) : match));
}

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
  const [skipWeekends, setSkipWeekends] = useState(false);
  const [excludedDates, setExcludedDates] = useState<string[]>([]);
  const [newDate, setNewDate] = useState('');
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
        setSkipWeekends(s.daily_report_skip_weekends);
        setExcludedDates(s.daily_report_excluded_dates);
      })
      .catch((err) => setError(err instanceof Error ? err.message : t('report.settingsLoadFailed')));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  function addExcludedDate() {
    if (!newDate || excludedDates.includes(newDate)) return;
    setExcludedDates((prev) => [...prev, newDate].sort());
    setNewDate('');
  }

  function removeExcludedDate(date: string) {
    setExcludedDates((prev) => prev.filter((d) => d !== date));
  }

  async function save() {
    if (!token) return;
    setSaving(true);
    setSaved(false);
    setError(null);
    try {
      const updated = await apiFetch<DailyReportSettings>('/reports/daily/settings', {
        method: 'PATCH',
        token,
        body: {
          daily_report_enabled: enabled,
          daily_report_time: time,
          daily_report_timezone: tz,
          daily_report_skip_weekends: skipWeekends,
          daily_report_excluded_dates: excludedDates,
        },
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

  const dirty =
    enabled !== settings.daily_report_enabled ||
    time !== settings.daily_report_time ||
    tz !== settings.daily_report_timezone ||
    skipWeekends !== settings.daily_report_skip_weekends ||
    JSON.stringify(excludedDates) !== JSON.stringify(settings.daily_report_excluded_dates);

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
      </div>

      <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13.5, marginBottom: 14, cursor: enabled ? 'pointer' : 'default', opacity: enabled ? 1 : 0.5 }}>
        <input type="checkbox" checked={skipWeekends} onChange={(e) => setSkipWeekends(e.target.checked)} disabled={!enabled} />
        {t('report.settingsSkipWeekends')}
      </label>

      <div style={{ marginBottom: 16, opacity: enabled ? 1 : 0.5 }}>
        <div style={{ fontSize: 12, color: 'var(--color-text-muted)', marginBottom: 6 }}>{t('report.settingsExcludedDates')}</div>
        <div style={{ display: 'flex', gap: 8, marginBottom: 10 }}>
          <input type="date" value={newDate} onChange={(e) => setNewDate(e.target.value)} className="input" style={{ width: 160 }} disabled={!enabled} />
          <button type="button" className="btn btn-secondary" onClick={addExcludedDate} disabled={!enabled || !newDate}>
            {t('report.settingsAddDate')}
          </button>
        </div>
        {excludedDates.length === 0 ? (
          <p style={{ fontSize: 12.5, color: 'var(--color-text-subtle)', margin: 0 }}>{t('report.settingsNoExcludedDates')}</p>
        ) : (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
            {excludedDates.map((date) => (
              <span
                key={date}
                className="badge"
                style={{ background: 'var(--color-bg)', color: 'var(--color-text-muted)', display: 'inline-flex', alignItems: 'center', gap: 6 }}
              >
                {date}
                <button
                  type="button"
                  onClick={() => removeExcludedDate(date)}
                  disabled={!enabled}
                  aria-label={t('report.settingsRemoveDate')}
                  style={{ background: 'none', border: 'none', cursor: enabled ? 'pointer' : 'default', color: 'inherit', padding: 0, fontSize: 13, lineHeight: 1 }}
                >
                  ×
                </button>
              </span>
            ))}
          </div>
        )}
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <button type="button" className="btn btn-primary" onClick={save} disabled={saving || !dirty}>
          {t('report.settingsSave')}
        </button>
        {saved && (
          <span style={{ fontSize: 13, color: 'var(--status-completed-text)' }}>{t('report.settingsSaved')}</span>
        )}
      </div>
    </div>
  );
}

function TemplateSettings() {
  const { token } = useAuth();
  const { t } = useLocale();
  const [settings, setSettings] = useState<DailyReportSettings | null>(null);
  const [lang, setLang] = useState<string>('en');
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!token) return;
    apiFetch<DailyReportSettings>('/reports/daily/settings', { token })
      .then((s) => {
        setSettings(s);
        setDraft(s.daily_report_template);
      })
      .catch((err) => setError(err instanceof Error ? err.message : t('report.template.loadFailed')));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  async function save() {
    if (!token || !settings) return;
    setSaving(true);
    setSaved(false);
    setError(null);
    try {
      const updated = await apiFetch<DailyReportSettings>('/reports/daily/settings', {
        method: 'PATCH',
        token,
        body: { daily_report_template: { [lang]: draft[lang] } },
      });
      setSettings(updated);
      setDraft(updated.daily_report_template);
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t('report.template.saveFailed'));
    } finally {
      setSaving(false);
    }
  }

  async function resetToDefault() {
    if (!token) return;
    setSaving(true);
    setSaved(false);
    setError(null);
    try {
      const updated = await apiFetch<DailyReportSettings>('/reports/daily/settings', {
        method: 'PATCH',
        token,
        body: { daily_report_template: { [lang]: null } },
      });
      setSettings(updated);
      setDraft(updated.daily_report_template);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t('report.template.saveFailed'));
    } finally {
      setSaving(false);
    }
  }

  if (!settings) return null;

  const isCustom = settings.daily_report_template_custom[lang];
  const dirty = draft[lang] !== settings.daily_report_template[lang];

  return (
    <div className="card card-pad" style={{ marginBottom: 24 }}>
      <h2 style={{ fontSize: 15, marginTop: 0, marginBottom: 4 }}>{t('report.template.title')}</h2>
      <p style={{ fontSize: 12.5, color: 'var(--color-text-subtle)', marginTop: 0, marginBottom: 14 }}>{t('report.template.hint')}</p>

      {error && (
        <div style={{ padding: 12, borderRadius: 10, background: 'var(--color-danger-soft)', color: 'var(--color-danger)', marginBottom: 14, fontSize: 13 }}>
          {error}
        </div>
      )}

      <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
        {LOCALES.map((locale) => (
          <button
            key={locale.code}
            type="button"
            className={`btn ${lang === locale.code ? 'btn-accent' : 'btn-secondary'}`}
            onClick={() => setLang(locale.code)}
            style={{ display: 'flex', alignItems: 'center', gap: 6 }}
          >
            {locale.label}
            {settings.daily_report_template_custom[locale.code] && (
              <span style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--color-accent)', display: 'inline-block' }} />
            )}
          </button>
        ))}
        <span style={{ marginLeft: 'auto', fontSize: 12.5, color: isCustom ? 'var(--color-accent-text)' : 'var(--color-text-subtle)', alignSelf: 'center' }}>
          {isCustom ? t('report.template.custom') : t('report.template.default')}
        </span>
      </div>

      <textarea
        value={draft[lang] ?? ''}
        onChange={(e) => setDraft((prev) => ({ ...prev, [lang]: e.target.value }))}
        className="input"
        rows={5}
        style={{ width: '100%', fontFamily: 'inherit', resize: 'vertical', marginBottom: 12 }}
      />

      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 14 }}>
        <button type="button" className="btn btn-primary" onClick={save} disabled={saving || !dirty}>
          {t('report.template.save')}
        </button>
        <button type="button" className="btn btn-secondary" onClick={resetToDefault} disabled={saving || !isCustom}>
          {t('report.template.reset')}
        </button>
        {saved && <span style={{ fontSize: 13, color: 'var(--status-completed-text)' }}>{t('report.template.saved')}</span>}
      </div>

      <div style={{ fontSize: 12, color: 'var(--color-text-subtle)', marginBottom: 6 }}>{t('report.template.preview')}</div>
      <div
        style={{
          padding: 12,
          borderRadius: 10,
          background: 'var(--color-bg)',
          fontSize: 13,
          whiteSpace: 'pre-wrap',
          wordBreak: 'break-word',
        }}
      >
        {renderPreview(draft[lang] ?? '')}
      </div>
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
  const { t, formatDate } = useLocale();
  const { label: serviceLabel } = useServices();
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

      {isAdminRole(user?.role) && (
        <>
          <DeliverySettings />
          <TemplateSettings />
        </>
      )}

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
                    <span style={{ fontSize: 13.5, color: 'var(--color-text-muted)' }}>{serviceLabel(row.category)}</span>
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
                      <div style={{ fontSize: 12, color: 'var(--color-text-subtle)', marginTop: 3 }}>{serviceLabel(ticket.category)}</div>
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
