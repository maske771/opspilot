'use client';

import { useCallback, useEffect, useState } from 'react';
import { Nav } from '../components/Nav';
import { RequireAuth, useAuth } from '../lib/auth';
import { apiFetch, ApiError, type CustomerRead } from '../lib/api';

function CustomersList() {
  const { token, user } = useAuth();
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
      .catch((err) => setError(err instanceof Error ? err.message : 'Не удалось загрузить клиентов'))
      .finally(() => setLoading(false));
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
      setError(err instanceof ApiError ? err.message : 'Не удалось создать клиента');
    } finally {
      setCreating(false);
    }
  }

  return (
    <>
      <Nav />
      <main style={{ maxWidth: 900, margin: '0 auto', padding: 32 }}>
        <h1 style={{ fontSize: 26, marginBottom: 20 }}>Customers</h1>

        <form
          onSubmit={createCustomer}
          style={{
            display: 'flex',
            gap: 10,
            marginBottom: 24,
            padding: 16,
            border: '1px solid #e5e7eb',
            borderRadius: 12,
            background: '#fff',
          }}
        >
          <input required placeholder="Имя" value={name} onChange={(e) => setName(e.target.value)} style={{ ...input, flex: 1 }} />
          <input placeholder="Телефон" value={phone} onChange={(e) => setPhone(e.target.value)} style={{ ...input, flex: 1 }} />
          <input placeholder="Email" value={email} onChange={(e) => setEmail(e.target.value)} style={{ ...input, flex: 1 }} />
          <button type="submit" disabled={creating} style={button}>
            {creating ? 'Добавление...' : 'Добавить'}
          </button>
        </form>

        {error && (
          <div style={{ padding: 14, borderRadius: 10, background: '#fee2e2', color: '#991b1b', marginBottom: 20 }}>
            {error}
          </div>
        )}

        {loading ? (
          <p style={{ color: '#6b7280' }}>Загрузка...</p>
        ) : customers.length === 0 ? (
          <div style={{ border: '1px dashed #d1d5db', borderRadius: 16, padding: 40, textAlign: 'center', color: '#6b7280' }}>
            Клиентов пока нет.
          </div>
        ) : (
          <div style={{ border: '1px solid #e5e7eb', borderRadius: 14, overflow: 'hidden', background: '#fff' }}>
            {customers.map((customer) => (
              <div
                key={customer.id}
                style={{
                  display: 'grid',
                  gridTemplateColumns: '1.4fr 1fr 1fr',
                  gap: 12,
                  padding: 16,
                  borderBottom: '1px solid #f0f0f0',
                }}
              >
                <div style={{ fontWeight: 600 }}>{customer.name ?? '—'}</div>
                <div style={{ fontSize: 13, color: '#6b7280' }}>{customer.phone ?? '—'}</div>
                <div style={{ fontSize: 13, color: '#6b7280' }}>{customer.email ?? '—'}</div>
              </div>
            ))}
          </div>
        )}
      </main>
    </>
  );
}

const input: React.CSSProperties = {
  padding: '9px 12px',
  borderRadius: 8,
  border: '1px solid #d1d5db',
  fontSize: 14,
};
const button: React.CSSProperties = {
  padding: '9px 16px',
  borderRadius: 8,
  border: 0,
  background: '#111827',
  color: '#fff',
  fontSize: 14,
  cursor: 'pointer',
  whiteSpace: 'nowrap',
};

export default function CustomersPage() {
  return (
    <RequireAuth>
      <CustomersList />
    </RequireAuth>
  );
}
