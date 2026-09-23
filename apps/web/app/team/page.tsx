'use client';

import { useCallback, useEffect, useState } from 'react';
import { Nav } from '../components/Nav';
import { RequireAuth, useAuth } from '../lib/auth';
import { apiFetch, ApiError, type UserRead, type UserRole } from '../lib/api';
import { useLocale } from '../lib/locale';
import { isAdminRole } from '../lib/roles';

const ASSIGNABLE_ROLES = ['staff', 'technician'];

const CREATABLE_ROLES: UserRole[] = ['admin', 'manager', 'staff', 'technician'];

const CATEGORIES = ['emergency', 'plumbing', 'electrical', 'hvac', 'appliance', 'access'];

function TeamPage() {
  const { token, user } = useAuth();
  const { t, tOr } = useLocale();
  const [users, setUsers] = useState<UserRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [savingId, setSavingId] = useState<string | null>(null);

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [role, setRole] = useState<UserRole>('technician');
  const [creating, setCreating] = useState(false);

  const load = useCallback(() => {
    if (!token) return;
    setLoading(true);
    apiFetch<UserRead[]>('/users', { token })
      .then(setUsers)
      .catch((err) => setError(err instanceof Error ? err.message : t('team.loadFailed')))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  useEffect(() => {
    load();
  }, [load]);

  async function createUser(e: React.FormEvent) {
    e.preventDefault();
    if (!token) return;
    setCreating(true);
    setError(null);
    try {
      await apiFetch('/users', {
        method: 'POST',
        token,
        body: { email, password, role },
      });
      setEmail('');
      setPassword('');
      setRole('technician');
      load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t('team.createFailed'));
    } finally {
      setCreating(false);
    }
  }

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
      setError(err instanceof ApiError ? err.message : t('team.saveFailed'));
    } finally {
      setSavingId(null);
    }
  }

  if (!isAdminRole(user?.role)) {
    return (
      <>
        <Nav />
        <main className="page">
          <div className="empty-state">{t('common.ownerAdminOnly')}</div>
        </main>
      </>
    );
  }

  return (
    <>
      <Nav />
      <main className="page">
        <h1 className="page-title">{t('nav.team')}</h1>
        <p className="page-subtitle">{t('team.subtitle')}</p>

        <form onSubmit={createUser} className="card card-pad" style={{ display: 'flex', gap: 10, marginBottom: 24 }}>
          <input
            required
            type="email"
            placeholder={t('auth.email')}
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="input"
            style={{ flex: 1 }}
          />
          <input
            required
            type="password"
            placeholder={t('auth.password')}
            minLength={8}
            autoComplete="new-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="input"
            style={{ flex: 1 }}
          />
          <select value={role} onChange={(e) => setRole(e.target.value as UserRole)} className="input">
            {CREATABLE_ROLES.map((r) => (
              <option key={r} value={r}>
                {tOr(`role.${r}`, r)}
              </option>
            ))}
          </select>
          <button type="submit" disabled={creating} className="btn btn-accent">
            {creating ? t('common.adding') : t('team.addEmployee')}
          </button>
        </form>

        {error && (
          <div style={{ padding: 14, borderRadius: 10, background: 'var(--color-danger-soft)', color: 'var(--color-danger)', marginBottom: 20 }}>
            {error}
          </div>
        )}

        {loading ? (
          <p style={{ color: 'var(--color-text-muted)' }}>{t('common.loading')}</p>
        ) : users.length === 0 ? (
          <div className="empty-state">{t('team.empty')}</div>
        ) : (
          <div className="card">
            {users.map((member) => (
              <div key={member.id} className="list-row">
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: ASSIGNABLE_ROLES.includes(member.role) ? 10 : 0 }}>
                  <div style={{ fontWeight: 600, fontSize: 14 }}>{member.email}</div>
                  <span className="badge" style={{ background: 'var(--color-bg)', color: 'var(--color-text-muted)' }}>
                    {tOr(`role.${member.role}`, member.role)}
                  </span>
                </div>
                {ASSIGNABLE_ROLES.includes(member.role) && (
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
                          {tOr(`category.${category}`, category)}
                        </button>
                      );
                    })}
                  </div>
                )}
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
