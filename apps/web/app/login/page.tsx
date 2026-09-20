'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '../lib/auth';
import { ApiError } from '../lib/api';

export default function LoginPage() {
  const { login } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await login(email, password);
      router.push('/');
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось войти');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main style={{ maxWidth: 380, margin: '80px auto', padding: 24 }}>
      <h1 style={{ fontSize: 24, marginBottom: 24 }}>OpsPilot</h1>
      <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        <label style={fieldLabel}>
          Email
          <input
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            style={input}
          />
        </label>
        <label style={fieldLabel}>
          Пароль
          <input
            type="password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            style={input}
          />
        </label>
        {error && <div style={{ color: '#991b1b', fontSize: 13 }}>{error}</div>}
        <button type="submit" disabled={submitting} style={button}>
          {submitting ? 'Вход...' : 'Войти'}
        </button>
      </form>
      <p style={{ marginTop: 16, fontSize: 13, color: '#6b7280' }}>
        Нет аккаунта? <a href="/register">Зарегистрировать компанию</a>
      </p>
    </main>
  );
}

const fieldLabel: React.CSSProperties = {
  display: 'flex',
  flexDirection: 'column',
  gap: 6,
  fontSize: 13,
  color: '#374151',
};
const input: React.CSSProperties = {
  padding: '10px 12px',
  borderRadius: 8,
  border: '1px solid #d1d5db',
  fontSize: 14,
};
const button: React.CSSProperties = {
  padding: '10px 16px',
  borderRadius: 8,
  border: 0,
  background: '#111827',
  color: '#fff',
  fontSize: 14,
  cursor: 'pointer',
  marginTop: 8,
};
