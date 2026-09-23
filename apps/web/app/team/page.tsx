'use client';

import { useCallback, useEffect, useState } from 'react';
import { Nav } from '../components/Nav';
import { RequireAuth, useAuth } from '../lib/auth';
import { apiFetch, ApiError, type UserRead } from '../lib/api';
import { isAdminRole } from '../lib/roles';

const ASSIGNABLE_ROLES = ['staff', 'technician'];

const CATEGORIES = ['emergency', 'plumbing', 'electrical', 'hvac', 'appliance', 'access'];

function TeamPage() {
  const { token, user } = useAuth();
  const [users, setUsers] = useState<UserRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [savingId, setSavingId] = useState<string | null>(null);

  const load = useCallback(() => {
    if (!token) return;
    setLoading(true);
    apiFetch<UserRead[]>('/users', { token })
      .then(setUsers)
      .catch((err) => setError(err instanceof Error ? err.message : 'Не удалось загрузить сотрудников'))
      .finally(() => setLoading(false));
  }, [token]);

  useEffect(() => {
    load();
  }, [load]);

  async function toggleSpecialty(target: UserRead, category: string) {
    if (!token) return;
    const next = target.specialties.includes(category)
      ? target.specialties.filter((c) => c !== category)
      : [...target.specialties, category];

    setUsers((prev) => prev.map((u) => (u.id === target.id ? { ...u, specialties: next } : u)));
    setSavingId(target.id);
    setError(null);
    try {
      await apiFetch(`/users/${target.id}/specialties`, {
        method: 'PATCH',
        token,
        body: { specialties: next },
      });
    } catch (err) {
      setUsers((prev) => prev.map((u) => (u.id === target.id ? target : u)));
      setError(err instanceof ApiError ? err.message : 'Не удалось сохранить специализацию');
    } finally {
      setSavingId(null);
    }
  }

  if (!isAdminRole(user?.role)) {
    return (
      <>
        <Nav />
        <main className="page">
          <div className="empty-state">Доступно только владельцу и админу.</div>
        </main>
      </>
    );
  }

  const staff = users.filter((u) => ASSIGNABLE_ROLES.includes(u.role));

  return (
    <>
      <Nav />
      <main className="page">
        <h1 className="page-title">Team</h1>
        <p className="page-subtitle">
          Специализации staff/technician — по ним движок назначения подбирает исполнителя под тематику заявки.
        </p>

        {error && (
          <div style={{ padding: 14, borderRadius: 10, background: 'var(--color-danger-soft)', color: 'var(--color-danger)', marginBottom: 20 }}>
            {error}
          </div>
        )}

        {loading ? (
          <p style={{ color: 'var(--color-text-muted)' }}>Загрузка...</p>
        ) : staff.length === 0 ? (
          <div className="empty-state">Пока нет сотрудников с ролью staff/technician.</div>
        ) : (
          <div className="card">
            {staff.map((member) => (
              <div key={member.id} className="list-row">
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
                  <div style={{ fontWeight: 600, fontSize: 14 }}>{member.email}</div>
                  <span className="badge" style={{ background: 'var(--color-bg)', color: 'var(--color-text-muted)' }}>
                    {member.role}
                  </span>
                </div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                  {CATEGORIES.map((category) => {
                    const active = member.specialties.includes(category);
                    return (
                      <button
                        key={category}
                        type="button"
                        disabled={savingId === member.id}
                        onClick={() => toggleSpecialty(member, category)}
                        className="badge"
                        style={{
                          cursor: 'pointer',
                          border: '1px solid var(--color-border)',
                          background: active ? 'var(--color-accent)' : 'var(--color-surface)',
                          color: active ? '#fff' : 'var(--color-text-muted)',
                        }}
                      >
                        {category}
                      </button>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>
        )}
      </main>
    </>
  );
}

export default function Team() {
  return (
    <RequireAuth>
      <TeamPage />
    </RequireAuth>
  );
}
