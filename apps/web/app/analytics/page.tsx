'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { RequireAuth, useAuth } from '../lib/auth';
import { apiFetch, type AnalyticsOverview, type DayVolume } from '../lib/api';
import { useLocale } from '../lib/locale';
import { isManagerRole } from '../lib/roles';

const PRESETS = [7, 30, 90] as const;

function shiftDate(iso: string, days: number): string {
  const d = new Date(iso + 'T00:00:00Z');
  d.setUTCDate(d.getUTCDate() + days);
  return d.toISOString().slice(0, 10);
}

function formatDuration(minutes: number | null, t: (key: 'analytics.unit.day' | 'analytics.unit.hour' | 'analytics.unit.min') => string): string {
  if (minutes == null) return '—';
  if (minutes >= 1440) return `${(minutes / 1440).toFixed(1)}${t('analytics.unit.day')}`;
  if (minutes >= 60) return `${(minutes / 60).toFixed(1)}${t('analytics.unit.hour')}`;
  return `${Math.round(minutes)}${t('analytics.unit.min')}`;
}

function niceMax(value: number): number {
  if (value <= 0) return 4;
  const step = Math.pow(10, Math.floor(Math.log10(value)));
  const normalized = value / step;
  const niceNormalized = normalized <= 2 ? 2 : normalized <= 5 ? 5 : 10;
  return niceNormalized * step;
}

function VolumeChart({ volume }: { volume: DayVolume[] }) {
  const { t, formatDate } = useLocale();
  const svgRef = useRef<SVGSVGElement>(null);
  const [hoverIndex, setHoverIndex] = useState<number | null>(null);

  const width = 720;
  const height = 220;
  const padLeft = 36;
  const padRight = 12;
  const padTop = 12;
  const padBottom = 24;
  const plotW = width - padLeft - padRight;
  const plotH = height - padTop - padBottom;

  const max = niceMax(Math.max(1, ...volume.map((v) => Math.max(v.created, v.closed))));
  const n = volume.length;
  const x = (i: number) => padLeft + (n <= 1 ? plotW / 2 : (i / (n - 1)) * plotW);
  const y = (v: number) => padTop + plotH - (v / max) * plotH;

  const linePath = (key: 'created' | 'closed') => volume.map((v, i) => `${i === 0 ? 'M' : 'L'} ${x(i)} ${y(v[key])}`).join(' ');

  const totalCreated = volume.reduce((sum, v) => sum + v.created, 0);
  const totalClosed = volume.reduce((sum, v) => sum + v.closed, 0);

  function handleMove(e: React.PointerEvent<SVGSVGElement>) {
    const svg = svgRef.current;
    if (!svg || n === 0) return;
    const rect = svg.getBoundingClientRect();
    const px = ((e.clientX - rect.left) / rect.width) * width;
    const ratio = n <= 1 ? 0 : (px - padLeft) / plotW;
    const idx = Math.min(n - 1, Math.max(0, Math.round(ratio * (n - 1))));
    setHoverIndex(idx);
  }

  const ticks = [0, max / 2, max];
  const hovered = hoverIndex != null ? volume[hoverIndex] : null;

  return (
    <div>
      <div style={{ display: 'flex', gap: 20, marginBottom: 10, fontSize: 13 }}>
        <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <svg width="14" height="4" aria-hidden="true">
            <rect width="14" height="3" rx="1.5" fill="var(--chart-created)" />
          </svg>
          {t('analytics.created')} <strong>{totalCreated}</strong>
        </span>
        <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <svg width="14" height="4" aria-hidden="true">
            <rect width="14" height="3" rx="1.5" fill="var(--chart-closed)" />
          </svg>
          {t('analytics.closed')} <strong>{totalClosed}</strong>
        </span>
      </div>
      <svg
        ref={svgRef}
        viewBox={`0 0 ${width} ${height}`}
        width="100%"
        style={{ display: 'block', touchAction: 'none' }}
        onPointerMove={handleMove}
        onPointerLeave={() => setHoverIndex(null)}
        role="img"
        aria-label={t('analytics.volumeChartLabel')}
      >
        {ticks.map((tick) => (
          <g key={tick}>
            <line x1={padLeft} x2={width - padRight} y1={y(tick)} y2={y(tick)} stroke="var(--color-border-subtle)" strokeWidth={1} />
            <text x={padLeft - 8} y={y(tick)} textAnchor="end" dominantBaseline="middle" fontSize={10} fill="var(--color-text-subtle)">
              {Math.round(tick)}
            </text>
          </g>
        ))}

        <path d={linePath('created')} fill="none" stroke="var(--chart-created)" strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />
        <path d={linePath('closed')} fill="none" stroke="var(--chart-closed)" strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />

        {n > 0 && (
          <>
            <circle cx={x(n - 1)} cy={y(volume[n - 1].created)} r={4} fill="var(--chart-created)" stroke="var(--color-surface)" strokeWidth={2} />
            <circle cx={x(n - 1)} cy={y(volume[n - 1].closed)} r={4} fill="var(--chart-closed)" stroke="var(--color-surface)" strokeWidth={2} />
          </>
        )}

        {hoverIndex != null && (
          <>
            <line x1={x(hoverIndex)} x2={x(hoverIndex)} y1={padTop} y2={padTop + plotH} stroke="var(--color-text-subtle)" strokeWidth={1} />
            <circle cx={x(hoverIndex)} cy={y(volume[hoverIndex].created)} r={4} fill="var(--chart-created)" stroke="var(--color-surface)" strokeWidth={2} />
            <circle cx={x(hoverIndex)} cy={y(volume[hoverIndex].closed)} r={4} fill="var(--chart-closed)" stroke="var(--color-surface)" strokeWidth={2} />
          </>
        )}
      </svg>
      <div style={{ minHeight: 20, fontSize: 12.5, color: 'var(--color-text-muted)', marginTop: 4 }}>
        {hovered && (
          <>
            {formatDate(hovered.date)} — {t('analytics.created')} <strong style={{ color: 'var(--color-text)' }}>{hovered.created}</strong>,{' '}
            {t('analytics.closed')} <strong style={{ color: 'var(--color-text)' }}>{hovered.closed}</strong>
          </>
        )}
      </div>
    </div>
  );
}

function BarList({
  rows,
  emptyLabel,
}: {
  rows: { key: string; label: string; value: number; sub?: string }[];
  emptyLabel: string;
}) {
  if (rows.length === 0) return <p style={{ fontSize: 13, color: 'var(--color-text-subtle)', margin: 0 }}>{emptyLabel}</p>;
  const max = Math.max(1, ...rows.map((r) => r.value));
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      {rows.map((row) => (
        <div key={row.key} title={`${row.label}: ${row.value}`}>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13, marginBottom: 3 }}>
            <span style={{ color: 'var(--color-text)' }}>{row.label}</span>
            <span style={{ color: 'var(--color-text-muted)', display: 'flex', gap: 8 }}>
              {row.sub && <span>{row.sub}</span>}
              <strong style={{ color: 'var(--color-text)' }}>{row.value}</strong>
            </span>
          </div>
          <div style={{ height: 8, background: 'var(--color-border-subtle)', borderRadius: 4 }}>
            <div style={{ height: 8, width: `${(row.value / max) * 100}%`, background: 'var(--color-accent)', borderRadius: 4 }} />
          </div>
        </div>
      ))}
    </div>
  );
}

function SlaMeter({ title, bucket, t }: { title: string; bucket: { met: number; missed: number; pending: number; met_pct: number | null }; t: ReturnType<typeof useLocale>['t'] }) {
  const pct = bucket.met_pct;
  const color = pct == null ? 'var(--color-text-subtle)' : pct >= 90 ? 'var(--status-completed-text)' : pct >= 75 ? 'var(--priority-high-text)' : 'var(--priority-critical-text)';
  return (
    <div className="card card-pad">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 8 }}>
        <h3 style={{ fontSize: 14, margin: 0 }}>{title}</h3>
        <span style={{ fontSize: 20, fontWeight: 700, color }}>{pct == null ? '—' : `${pct}%`}</span>
      </div>
      <div style={{ height: 8, background: 'var(--color-border-subtle)', borderRadius: 4, marginBottom: 10 }}>
        <div style={{ height: 8, width: `${pct ?? 0}%`, background: color, borderRadius: 4 }} />
      </div>
      <div style={{ display: 'flex', gap: 16, fontSize: 12.5, color: 'var(--color-text-muted)' }}>
        <span>{t('analytics.slaMet')}: <strong style={{ color: 'var(--color-text)' }}>{bucket.met}</strong></span>
        <span>{t('analytics.slaMissed')}: <strong style={{ color: 'var(--color-text)' }}>{bucket.missed}</strong></span>
        <span>{t('analytics.slaPending')}: <strong style={{ color: 'var(--color-text)' }}>{bucket.pending}</strong></span>
      </div>
    </div>
  );
}

function AnalyticsView() {
  const { token, user } = useAuth();
  const { t, tOr } = useLocale();
  const [data, setData] = useState<AnalyticsOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [range, setRange] = useState<{ from: string; to: string } | null>(null);
  const [activePreset, setActivePreset] = useState<number>(30);

  const load = useCallback(
    (from?: string, to?: string) => {
      if (!token) return;
      setLoading(true);
      const qs = from && to ? `?from=${from}&to=${to}` : '';
      apiFetch<AnalyticsOverview>(`/analytics/overview${qs}`, { token })
        .then((res) => {
          setData(res);
          setRange({ from: res.period_start, to: res.period_end });
        })
        .catch((err) => setError(err instanceof Error ? err.message : t('analytics.loadFailed')))
        .finally(() => setLoading(false));
      // eslint-disable-next-line react-hooks/exhaustive-deps
    },
    [token],
  );

  useEffect(() => {
    load();
  }, [load]);

  function applyPreset(days: number) {
    setActivePreset(days);
    const to = range?.to ?? new Date().toISOString().slice(0, 10);
    load(shiftDate(to, -(days - 1)), to);
  }

  const categoryRows = useMemo(
    () =>
      (data?.by_category ?? []).map((row) => ({
        key: row.category,
        label: tOr(`category.${row.category}`, row.category),
        value: row.created,
        sub: row.avg_resolution_minutes != null ? formatDuration(row.avg_resolution_minutes, t) : undefined,
      })),
    [data, t, tOr],
  );
  const propertyRows = useMemo(
    () => (data?.by_property ?? []).map((row) => ({ key: row.property_id, label: row.name, value: row.created })),
    [data],
  );
  const staffRows = useMemo(
    () =>
      (data?.by_staff ?? []).map((row) => ({
        key: row.user_id,
        label: row.email.split('@')[0],
        value: row.closed,
        sub: row.avg_resolution_minutes != null ? formatDuration(row.avg_resolution_minutes, t) : undefined,
      })),
    [data, t],
  );

  if (!isManagerRole(user?.role)) {
    return (
      <main className="page">
        <div className="empty-state">{t('common.managersOnly')}</div>
      </main>
    );
  }

  return (
    <main className="page">
      <h1 className="page-title">{t('nav.analytics')}</h1>
      <p className="page-subtitle">{t('analytics.subtitle')}</p>

      <div style={{ display: 'flex', gap: 8, marginBottom: 20 }}>
        {PRESETS.map((days) => (
          <button
            key={days}
            type="button"
            className={`btn ${activePreset === days ? 'btn-accent' : 'btn-secondary'}`}
            onClick={() => applyPreset(days)}
          >
            {t(`analytics.last${days}` as 'analytics.last7' | 'analytics.last30' | 'analytics.last90')}
          </button>
        ))}
      </div>

      {error && (
        <div style={{ padding: 14, borderRadius: 10, background: 'var(--color-danger-soft)', color: 'var(--color-danger)', marginBottom: 20 }}>
          {error}
        </div>
      )}

      {loading && !data ? (
        <p style={{ color: 'var(--color-text-muted)' }}>{t('common.loading')}</p>
      ) : data ? (
        <div style={{ opacity: loading ? 0.6 : 1 }}>
          <section className="card card-pad" style={{ marginBottom: 20 }}>
            <h2 style={{ fontSize: 15, marginTop: 0, marginBottom: 14 }}>{t('analytics.volumeTitle')}</h2>
            <VolumeChart volume={data.volume} />
          </section>

          <section style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: 16, marginBottom: 20 }}>
            <SlaMeter title={t('analytics.slaResponse')} bucket={data.sla.response} t={t} />
            <SlaMeter title={t('analytics.slaResolution')} bucket={data.sla.resolution} t={t} />
          </section>

          <section style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 16 }}>
            <div className="card card-pad">
              <h2 style={{ fontSize: 15, marginTop: 0, marginBottom: 14 }}>{t('analytics.byCategory')}</h2>
              <BarList rows={categoryRows} emptyLabel={t('analytics.noData')} />
            </div>
            <div className="card card-pad">
              <h2 style={{ fontSize: 15, marginTop: 0, marginBottom: 14 }}>{t('analytics.byProperty')}</h2>
              <BarList rows={propertyRows} emptyLabel={t('analytics.noData')} />
            </div>
            <div className="card card-pad">
              <h2 style={{ fontSize: 15, marginTop: 0, marginBottom: 14 }}>{t('analytics.byStaff')}</h2>
              <BarList rows={staffRows} emptyLabel={t('analytics.noData')} />
            </div>
          </section>
        </div>
      ) : null}
    </main>
  );
}

export default function AnalyticsPage() {
  return (
    <RequireAuth>
      <AnalyticsView />
    </RequireAuth>
  );
}
