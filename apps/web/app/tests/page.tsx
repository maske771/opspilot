'use client';

import { useEffect, useState } from 'react';

type TestRun = {
  id: string;
  suite: string;
  commit_sha?: string;
  branch?: string;
  environment: string;
  status: string;
  total: number;
  passed: number;
  failed: number;
  skipped: number;
  errors: number;
  duration_ms: number;
  created_at?: string;
};

type TestCase = {
  node_id: string;
  name: string;
  file_path?: string;
  class_name?: string;
  status: string;
  duration_ms: number;
  message?: string;
};

const API = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

function Badge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    passed: 'background:#dcfce7;color:#166534',
    failed: 'background:#fee2e2;color:#991b1b',
    error: 'background:#fee2e2;color:#991b1b',
    skipped: 'background:#fef3c7;color:#92400e',
  };
  return <span style={{ ...pill, ...(styles[status] ? {} : { background: '#e5e7eb', color: '#374151' }) }}>{status}</span>;
}

const pill: React.CSSProperties = { display: 'inline-block', padding: '4px 9px', borderRadius: 999, fontSize: 12, fontWeight: 700 };

export default function TestCenterPage() {
  const [runs, setRuns] = useState<TestRun[]>([]);
  const [selected, setSelected] = useState<{ run: TestRun; tests: TestCase[] } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    try {
      setLoading(true);
      setError(null);
      const response = await fetch(`${API}/test-center/runs?limit=50`, { cache: 'no-store' });
      if (!response.ok) throw new Error(`API ${response.status}`);
      setRuns(await response.json());
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Не удалось загрузить результаты');
    } finally {
      setLoading(false);
    }
  }

  async function openRun(run: TestRun) {
    const response = await fetch(`${API}/test-center/runs/${run.id}`, { cache: 'no-store' });
    if (response.ok) setSelected(await response.json());
  }

  useEffect(() => { void load(); }, []);

  const latest = runs[0];
  const totals = runs.reduce((acc, run) => ({
    passed: acc.passed + run.passed,
    failed: acc.failed + run.failed,
    skipped: acc.skipped + run.skipped,
    errors: acc.errors + run.errors,
  }), { passed: 0, failed: 0, skipped: 0, errors: 0 });

  return (
    <main style={{ maxWidth: 1180, margin: '0 auto', padding: 32, fontFamily: 'Arial, sans-serif', color: '#111827' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 16, marginBottom: 28 }}>
        <div>
          <div style={{ fontSize: 13, color: '#6b7280', marginBottom: 6 }}>OpsPilot / Quality</div>
          <h1 style={{ margin: 0, fontSize: 34 }}>Test Center</h1>
          <p style={{ color: '#6b7280', marginTop: 8 }}>История запусков pytest и результаты каждого теста.</p>
        </div>
        <button onClick={() => void load()} style={{ padding: '10px 16px', borderRadius: 10, border: '1px solid #d1d5db', background: '#fff', cursor: 'pointer' }}>Обновить</button>
      </div>

      {latest && (
        <section style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 12, marginBottom: 24 }}>
          {[
            ['Последний запуск', `${latest.status} · ${latest.total}`],
            ['Passed', String(latest.passed)],
            ['Failed', String(latest.failed)],
            ['Skipped', String(latest.skipped)],
            ['Ошибки', String(latest.errors)],
          ].map(([label, value]) => (
            <div key={label} style={{ border: '1px solid #e5e7eb', borderRadius: 14, padding: 18, background: '#fff' }}>
              <div style={{ fontSize: 12, color: '#6b7280' }}>{label}</div>
              <div style={{ fontSize: 22, fontWeight: 800, marginTop: 8 }}>{value}</div>
            </div>
          ))}
        </section>
      )}

      {error && <div style={{ padding: 14, borderRadius: 10, background: '#fee2e2', color: '#991b1b', marginBottom: 20 }}>Ошибка: {error}</div>}
      {loading ? <p>Загрузка...</p> : runs.length === 0 ? (
        <div style={{ border: '1px dashed #d1d5db', borderRadius: 16, padding: 40, textAlign: 'center', color: '#6b7280' }}>
          <h2 style={{ color: '#111827' }}>Тесты ещё не опубликованы</h2>
          <p>После запуска pytest загрузите JUnit XML в Test Center командой из README/scripts.</p>
        </div>
      ) : (
        <>
          <div style={{ display: 'flex', gap: 18, marginBottom: 14, color: '#6b7280', fontSize: 13 }}>
            <span>Всего запусков: <b>{runs.length}</b></span>
            <span>Passed за историю: <b>{totals.passed}</b></span>
            <span>Failed: <b>{totals.failed}</b></span>
            <span>Skipped: <b>{totals.skipped}</b></span>
          </div>
          <div style={{ border: '1px solid #e5e7eb', borderRadius: 16, overflow: 'hidden', background: '#fff' }}>
            {runs.map((run) => (
              <button key={run.id} onClick={() => void openRun(run)} style={{ width: '100%', textAlign: 'left', display: 'grid', gridTemplateColumns: '1.4fr 1fr 110px 90px 90px 90px 120px', gap: 12, alignItems: 'center', padding: 16, border: 0, borderBottom: '1px solid #f0f0f0', background: '#fff', cursor: 'pointer' }}>
                <div><b>{run.suite}</b><div style={{ fontSize: 12, color: '#9ca3af', marginTop: 4 }}>{run.branch ?? '—'} {run.commit_sha ? `· ${run.commit_sha.slice(0, 8)}` : ''}</div></div>
                <div style={{ fontSize: 13, color: '#6b7280' }}>{run.environment}</div>
                <Badge status={run.status} />
                <div>✓ {run.passed}</div>
                <div>✕ {run.failed}</div>
                <div>– {run.skipped}</div>
                <div style={{ color: '#6b7280', fontSize: 13 }}>{run.duration_ms} ms</div>
              </button>
            ))}
          </div>
        </>
      )}

      {selected && (
        <div onClick={() => setSelected(null)} style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,.35)', padding: 30, overflow: 'auto' }}>
          <div onClick={(e) => e.stopPropagation()} style={{ maxWidth: 1000, margin: '20px auto', background: '#fff', borderRadius: 18, padding: 24 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start', gap: 16 }}>
              <div><h2 style={{ marginTop: 0 }}>{selected.run.suite} · {selected.run.environment}</h2><div style={{ color: '#6b7280', fontSize: 13 }}>{selected.run.commit_sha ?? 'commit не указан'}</div></div>
              <button onClick={() => setSelected(null)} style={{ border: 0, background: '#f3f4f6', borderRadius: 8, padding: '7px 11px', cursor: 'pointer' }}>Закрыть</button>
            </div>
            <div style={{ margin: '20px 0', display: 'flex', gap: 14, flexWrap: 'wrap' }}>
              <Badge status={selected.run.status} /><span>Passed {selected.run.passed}</span><span>Failed {selected.run.failed}</span><span>Skipped {selected.run.skipped}</span><span>Errors {selected.run.errors}</span>
            </div>
            <div style={{ borderTop: '1px solid #e5e7eb' }}>
              {selected.tests.map((test) => (
                <div key={test.node_id} style={{ padding: '14px 0', borderBottom: '1px solid #f0f0f0' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12 }}><b>{test.name}</b><Badge status={test.status} /></div>
                  <div style={{ marginTop: 6, color: '#6b7280', fontSize: 12 }}>{test.file_path ?? ''} · {test.duration_ms} ms</div>
                  {test.message && <pre style={{ whiteSpace: 'pre-wrap', color: '#991b1b', background: '#fff7f7', padding: 10, borderRadius: 8 }}>{test.message}</pre>}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </main>
  );
}
