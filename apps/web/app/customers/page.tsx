'use client';

import { useCallback, useEffect, useState } from 'react';
import { RequireAuth, useAuth } from '../lib/auth';
import { apiFetch, ApiError, type CustomerRead, type PropertyRead, type UnitRead } from '../lib/api';
import { useLocale } from '../lib/locale';
import { isManagerRole } from '../lib/roles';

function CustomerRow({
  customer,
  properties,
  canLink,
  onChange,
  onError,
}: {
  customer: CustomerRead;
  properties: PropertyRead[];
  canLink: boolean;
  onChange: (next: CustomerRead) => void;
  onError: (message: string) => void;
}) {
  const { token } = useAuth();
  const { t } = useLocale();
  const [units, setUnits] = useState<UnitRead[]>([]);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!token || !customer.property_id) {
      setUnits([]);
      return;
    }
    apiFetch<UnitRead[]>(`/properties/${customer.property_id}/units`, { token }).then(setUnits).catch(() => setUnits([]));
  }, [token, customer.property_id]);

  async function link(body: { property_id?: string | null; unit_id?: string | null }) {
    if (!token) return;
    setSaving(true);
    try {
      onChange(await apiFetch<CustomerRead>(`/customers/${customer.id}`, { method: 'PATCH', token, body }));
    } catch (err) {
      onError(err instanceof ApiError ? err.message : t('customers.linkFailed'));
    } finally {
      setSaving(false);
    }
  }

  const propertyName = properties.find((p) => p.id === customer.property_id)?.name;
  const unitNumber = units.find((u) => u.id === customer.unit_id)?.unit_number;

  return (
    <div className="list-row grid-row" style={{ '--cols': '1.2fr 1fr 1fr 1.2fr 0.8fr' } as React.CSSProperties}>
      <div style={{ fontWeight: 600, fontSize: 14 }}>{customer.name ?? '—'}</div>
      <div style={{ fontSize: 13, color: 'var(--color-text-muted)' }}>{customer.phone ?? '—'}</div>
      <div style={{ fontSize: 13, color: 'var(--color-text-muted)' }}>{customer.email ?? '—'}</div>
      {canLink ? (
        <>
          <select
            className="select"
            value={customer.property_id ?? ''}
            disabled={saving}
            aria-label={t('customers.property')}
            onChange={(e) => link({ property_id: e.target.value || null, unit_id: null })}
          >
            <option value="">{t('customers.noProperty')}</option>
            {properties.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
          <select
            className="select"
            value={customer.unit_id ?? ''}
            disabled={saving || !customer.property_id || units.length === 0}
            aria-label={t('customers.unit')}
            onChange={(e) => link({ property_id: customer.property_id, unit_id: e.target.value || null })}
          >
            <option value="">—</option>
            {units.map((u) => (
              <option key={u.id} value={u.id}>
                {u.unit_number}
              </option>
            ))}
          </select>
        </>
      ) : (
        <>
          <div style={{ fontSize: 13, color: 'var(--color-text-muted)' }}>{propertyName ?? t('customers.noProperty')}</div>
          <div style={{ fontSize: 13, color: 'var(--color-text-muted)' }}>{unitNumber ?? '—'}</div>
        </>
      )}
    </div>
  );
}

function CustomersList() {
  const { token, user } = useAuth();
  const { t } = useLocale();
  const [customers, setCustomers] = useState<CustomerRead[]>([]);
  const [properties, setProperties] = useState<PropertyRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [name, setName] = useState('');
  const [phone, setPhone] = useState('');
  const [email, setEmail] = useState('');
  const [creating, setCreating] = useState(false);

  const load = useCallback(() => {
    if (!token) return;
    setLoading(true);
    apiFetch<PropertyRead[]>('/properties', { token }).then(setProperties).catch(() => undefined);
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

  const canLink = isManagerRole(user?.role);

  return (
    <>
      <main className="page">
        <h1 className="page-title">{t('nav.customers')}</h1>
        <p className="page-subtitle">{t('customers.subtitle')}</p>

        <form onSubmit={createCustomer} className="card card-pad row-form" style={{ marginBottom: 24 }}>
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
              <CustomerRow
                key={customer.id}
                customer={customer}
                properties={properties}
                canLink={canLink}
                onError={setError}
                onChange={(next) => setCustomers((prev) => prev.map((c) => (c.id === next.id ? next : c)))}
              />
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
