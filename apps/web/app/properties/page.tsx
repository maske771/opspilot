'use client';

import { useCallback, useEffect, useState } from 'react';
import { RequireAuth, useAuth } from '../lib/auth';
import { apiFetch, ApiError, type PropertyRead, type UnitRead } from '../lib/api';
import Link from 'next/link';
import { useLocale } from '../lib/locale';
import { isAdminRole, isManagerRole } from '../lib/roles';

function PropertiesList() {
  const { token, user } = useAuth();
  const { t } = useLocale();
  const [properties, setProperties] = useState<PropertyRead[]>([]);
  const [units, setUnits] = useState<Record<string, UnitRead[]>>({});
  const [expanded, setExpanded] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [name, setName] = useState('');
  const [address, setAddress] = useState('');
  const [creating, setCreating] = useState(false);

  const [newUnitNumber, setNewUnitNumber] = useState('');
  const [addingUnit, setAddingUnit] = useState(false);

  const load = useCallback(() => {
    if (!token) return;
    setLoading(true);
    apiFetch<PropertyRead[]>('/properties', { token })
      .then(setProperties)
      .catch((err) => setError(err instanceof Error ? err.message : t('properties.loadFailed')))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  useEffect(() => {
    load();
  }, [load]);

  async function createProperty(e: React.FormEvent) {
    e.preventDefault();
    if (!token || !user) return;
    setCreating(true);
    setError(null);
    try {
      await apiFetch('/properties', {
        method: 'POST',
        token,
        body: { organization_id: user.organization_id, name, address: address || null },
      });
      setName('');
      setAddress('');
      load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t('properties.createFailed'));
    } finally {
      setCreating(false);
    }
  }

  async function regenerateCode(propertyId: string) {
    if (!token || !window.confirm(t('properties.regenerateConfirm'))) return;
    try {
      const updated = await apiFetch<PropertyRead>(`/properties/${propertyId}/regenerate-code`, { method: 'POST', token });
      setProperties((prev) => prev.map((p) => (p.id === updated.id ? updated : p)));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t('properties.createFailed'));
    }
  }

  async function toggleExpand(propertyId: string) {
    if (expanded === propertyId) {
      setExpanded(null);
      return;
    }
    setExpanded(propertyId);
    if (!units[propertyId] && token) {
      const list = await apiFetch<UnitRead[]>(`/properties/${propertyId}/units`, { token });
      setUnits((prev) => ({ ...prev, [propertyId]: list }));
    }
  }

  async function addUnit(propertyId: string, e: React.FormEvent) {
    e.preventDefault();
    if (!token || !newUnitNumber.trim()) return;
    setAddingUnit(true);
    try {
      const created = await apiFetch<UnitRead>(`/properties/${propertyId}/units`, {
        method: 'POST',
        token,
        body: { unit_number: newUnitNumber.trim() },
      });
      setUnits((prev) => ({ ...prev, [propertyId]: [...(prev[propertyId] ?? []), created] }));
      setNewUnitNumber('');
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t('properties.addUnitFailed'));
    } finally {
      setAddingUnit(false);
    }
  }

  return (
    <>
      <main className="page">
        <h1 className="page-title">{t('nav.properties')}</h1>
        <p className="page-subtitle">{t('properties.subtitle')}</p>

        <form onSubmit={createProperty} className="card card-pad" style={{ display: 'flex', gap: 10, marginBottom: 24 }}>
          <input required placeholder={t('properties.namePlaceholder')} value={name} onChange={(e) => setName(e.target.value)} className="input" style={{ flex: 1 }} />
          <input placeholder={t('properties.addressPlaceholder')} value={address} onChange={(e) => setAddress(e.target.value)} className="input" style={{ flex: 2 }} />
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
        ) : properties.length === 0 ? (
          <div className="empty-state">{t('properties.empty')}</div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {properties.map((property) => (
              <div key={property.id} className="card">
                <button
                  onClick={() => toggleExpand(property.id)}
                  style={{
                    width: '100%',
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    padding: 16,
                    border: 0,
                    background: 'transparent',
                    color: 'inherit',
                    cursor: 'pointer',
                    textAlign: 'left',
                  }}
                >
                  <div>
                    <div style={{ fontWeight: 600, fontSize: 14.5, display: 'flex', alignItems: 'center', gap: 8 }}>
                      {property.name}
                      <span className="badge" title={t('properties.codeHint')} style={{ background: 'var(--color-accent-soft)', color: 'var(--color-accent-text)', fontFamily: 'monospace', letterSpacing: '0.08em' }}>
                        {property.code}
                      </span>
                    </div>
                    {property.address && (
                      <div style={{ fontSize: 12.5, color: 'var(--color-text-subtle)', marginTop: 4 }}>{property.address}</div>
                    )}
                  </div>
                  <span style={{ fontSize: 13, color: 'var(--color-text-muted)' }}>
                    {expanded === property.id ? t('properties.hideUnits') : t('properties.units')}
                  </span>
                </button>
                {expanded === property.id && (
                  <div style={{ borderTop: '1px solid var(--color-border-subtle)', padding: 16 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap', marginBottom: 12, fontSize: 13 }}>
                      <span style={{ color: 'var(--color-text-muted)' }}>
                        {t('properties.codeLabel')}: <strong style={{ fontFamily: 'monospace', letterSpacing: '0.08em', color: 'var(--color-text)' }}>{property.code}</strong>
                      </span>
                      {isManagerRole(user?.role) && (
                        <button type="button" className="btn btn-secondary" style={{ fontSize: 12.5, padding: '5px 10px' }} onClick={() => regenerateCode(property.id)}>
                          {t('properties.regenerateCode')}
                        </button>
                      )}
                      {isAdminRole(user?.role) && (
                        <Link href={`/properties/${property.id}`} style={{ fontSize: 13.5, color: 'var(--color-accent-text)' }}>
                          {t('properties.servicesLink')} →
                        </Link>
                      )}
                    </div>
                    {(units[property.id] ?? []).length === 0 ? (
                      <p style={{ fontSize: 13, color: 'var(--color-text-subtle)', margin: '0 0 12px' }}>{t('properties.noUnits')}</p>
                    ) : (
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginBottom: 12 }}>
                        {(units[property.id] ?? []).map((unit) => (
                          <span key={unit.id} className="badge" style={{ background: 'var(--color-bg)', color: 'var(--color-text-muted)' }}>
                            {unit.unit_number}
                          </span>
                        ))}
                      </div>
                    )}
                    <form onSubmit={(e) => addUnit(property.id, e)} style={{ display: 'flex', gap: 8 }}>
                      <input
                        placeholder={t('properties.unitNumber')}
                        value={newUnitNumber}
                        onChange={(e) => setNewUnitNumber(e.target.value)}
                        className="input"
                        style={{ flex: 1 }}
                      />
                      <button type="submit" disabled={addingUnit} className="btn btn-secondary">
                        {addingUnit ? '...' : t('properties.addUnit')}
                      </button>
                    </form>
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

export default function PropertiesPage() {
  return (
    <RequireAuth>
      <PropertiesList />
    </RequireAuth>
  );
}
