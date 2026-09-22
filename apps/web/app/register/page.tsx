'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '../lib/auth';
import { apiFetch, ApiError } from '../lib/api';

export default function RegisterPage() {
  const { login } = useAuth();
  const router = useRouter();
  const [organizationName, setOrganizationName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await apiFetch('/auth/register', {
        method: 'POST',
        body: { organization_name: organizationName, email, password },
      });
      await login(email, password);
      router.push('/');
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось зарегистрироваться');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 24 }}>
      <div className="card card-pad" style={{ width: '100%', maxWidth: 380, boxShadow: 'var(--shadow-md)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 28 }}>
          <span className="nav-brand-mark" style={{ width: 28, height: 28, borderRadius: 9 }} />
          <span style={{ fontWeight: 800, fontSize: 18, letterSpacing: '-0.01em' }}>Новая компания</span>
        </div>
        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <label className="field">
            Название компании
            <input required value={organizationName} onChange={(e) => setOrganizationName(e.target.value)} className="input" />
          </label>
          <label className="field">
            Email
            <input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} className="input" />
          </label>
          <label className="field">
            Пароль
            <input type="password" required minLength={8} value={password} onChange={(e) => setPassword(e.target.value)} className="input" />
          </label>
          {error && <div style={{ color: 'var(--color-danger)', fontSize: 13 }}>{error}</div>}
          <button type="submit" disabled={submitting} className="btn btn-accent" style={{ marginTop: 6 }}>
            {submitting ? 'Создание...' : 'Создать аккаунт'}
          </button>
        </form>
        <p style={{ marginTop: 18, fontSize: 13, color: 'var(--color-text-muted)' }}>
          Уже есть аккаунт? <a href="/login" style={{ color: 'var(--color-accent)', fontWeight: 500 }}>Войти</a>
        </p>
      </div>
    </main>
  );
}
