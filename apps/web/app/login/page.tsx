'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Preferences } from '../components/Preferences';
import { useAuth } from '../lib/auth';
import { ApiError } from '../lib/api';
import { useLocale } from '../lib/locale';

export default function LoginPage() {
  const { login } = useAuth();
  const { t } = useLocale();
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
      setError(err instanceof ApiError ? err.message : t('auth.loginFailed'));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 24 }}>
      <div className="prefs-floating">
        <Preferences />
      </div>
      <div className="card card-pad" style={{ width: '100%', maxWidth: 380, boxShadow: 'var(--shadow-md)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 28 }}>
          <span className="nav-brand-mark" style={{ width: 28, height: 28, borderRadius: 9 }} />
          <span style={{ fontWeight: 800, fontSize: 18, letterSpacing: '-0.01em' }}>OpsPilot</span>
        </div>
        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <label className="field">
            {t('auth.email')}
            <input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} className="input" />
          </label>
          <label className="field">
            {t('auth.password')}
            <input type="password" required value={password} onChange={(e) => setPassword(e.target.value)} className="input" />
          </label>
          {error && <div style={{ color: 'var(--color-danger)', fontSize: 13 }}>{error}</div>}
          <button type="submit" disabled={submitting} className="btn btn-accent" style={{ marginTop: 6 }}>
            {submitting ? t('auth.signingIn') : t('auth.signIn')}
          </button>
        </form>
        <p style={{ marginTop: 18, fontSize: 13, color: 'var(--color-text-muted)' }}>
          {t('auth.noAccount')} <a href="/register" style={{ color: 'var(--color-accent)', fontWeight: 500 }}>{t('auth.registerCompany')}</a>
        </p>
      </div>
    </main>
  );
}
