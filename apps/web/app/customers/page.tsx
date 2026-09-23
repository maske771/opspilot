'use client';

import { useCallback, useEffect, useState } from 'react';
import { Nav } from '../components/Nav';
import { RequireAuth, useAuth } from '../lib/auth';
import { apiFetch, ApiError, type CustomerRead } from '../lib/api';
import { useLocale } from '../lib/locale';

function CustomersList() {
  const { token, user } = useAuth();
  const { t } = useLocale();
  const [customers, setCustomers] = useState<CustomerRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [name, setName] = useState('');
  const [phone, setPhone] = useState('');
  const [email, setEmail] = useState('');
  const [creating, setCreating] = useState(false);

  const load = useCallback(() => {
    if (!token) return;
    setLoading(true);
    apiFetch<CustomerRead[]>('/customers', { token })
      .then(setCustomers)
      .catch((err) => setError(err instanceof Error ? err.message : t('customers.loadFailed')))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  useEffect(() => {
    load();
  }, [load]);

  async function createCustomer(e: React.FormEvent) {
    e.preventDefault();
    if (!token || !user) return;
    setCreating(true);
    setError(null);
    try {
      await apiFetch('/customers', {
        method: 'POST',
        token,
        body: { organization_id: user.organization_id, name, phone: phone || null, email: email || null },
      });
      setName('');
      setPhone('');
      setEmail('');
      load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t('customers.createFailed'));
    } finally {
      setCreating(false);
    }
  }

  return (
    <>
      <Nav />
      <main className="page">
        <h1 className="page-title">{t('nav.customers')}</h1>
        <p className="page-subtitle">{t('customers.subtitle')}</p>

        <form onSubmit={createCustomer} className="card card-pad" style={{ display: 'flex', gap: 10, marginBottom: 24 }}>
          <input required placeholder={t('customers.name')} value={name} onChange={(e) => setName(e.target.value)} className="input" style={{ flex: 1 }} />
          <input placeholder={t('customers.phone')} value={phone} onChange={(e) => setPhone(e.target.value)} className="input" style={{ flex: 1 }} />
          <input placeholder={t('auth.email')} value={email} onChange={(e) => setEmail(e.target.value)} className="input" style={{ flex: 1 }} />
          <button type="submit" disabled={creating} className="btn btn-accent">
            {creating ? t('common.adding') : t('common.add')}
          </button>
        </form>

        {error && (
          <div style={{ padding: 14, borderRadius: 10, background: 'var(--color-danger-soft)', color: 'var(--color-danger)', marginBottom: 20 }}>
            {error}
          </div>
        )}

        {loading ? (
          <p style={{ color: 'var(--color-text-muted)' }}>{t('common.loading')}</p>
        ) : customers.length === 0 ? (
          <div className="empty-state">{t('customers.empty')}</div>
        ) : (
          <div className="card">
            {customers.map((customer) => (
              <div key={customer.id} className="list-row" style={{ display: 'grid', gridTemplateColumns: '1.4fr 1fr 1fr', gap: 12 }}>
                <div style={{ fontWeight: 600, fontSize: 14 }}>{customer.name ?? '—'}</div>
                <div style={{ fontSize: 13, color: 'var(--color-text-muted)' }}>{customer.phone ?? '—'}</div>
                <div style={{ fontSize: 13, color: 'var(--color-text-muted)' }}>{customer.email ?? '—'}</div>
              </div>
            ))}
          </div>
        )}
      </main>
    </>
  );
}

export default function CustomersPage() {
  return (
    <RequireAuth>
      <CustomersList />
    </RequireAuth>
  );
}
