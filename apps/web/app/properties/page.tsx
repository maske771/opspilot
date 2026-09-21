'use client';

import { useCallback, useEffect, useState } from 'react';
import { Nav } from '../components/Nav';
import { RequireAuth, useAuth } from '../lib/auth';
import { apiFetch, ApiError, type PropertyRead, type UnitRead } from '../lib/api';

function PropertiesList() {
  const { token, user } = useAuth();
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
      .catch((err) => setError(err instanceof Error ? err.message : 'Не удалось загрузить объекты'))
      .finally(() => setLoading(false));
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
      setError(err instanceof ApiError ? err.message : 'Не удалось создать объект');
    } finally {
      setCreating(false);
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
      setError(err instanceof ApiError ? err.message : 'Не удалось добавить юнит');
    } finally {
      setAddingUnit(false);
    }
  }

  return (
    <>
      <Nav />
      <main style={{ maxWidth: 900, margin: '0 auto', padding: 32 }}>
        <h1 style={{ fontSize: 26, marginBottom: 20 }}>Properties</h1>

        <form
          onSubmit={createProperty}
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
          <input
            required
            placeholder="Название объекта"
            value={name}
            onChange={(e) => setName(e.target.value)}
            style={{ ...input, flex: 1 }}
          />
          <input
            placeholder="Адрес (необязательно)"
            value={address}
            onChange={(e) => setAddress(e.target.value)}
            style={{ ...input, flex: 2 }}
          />
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
        ) : properties.length === 0 ? (
          <div style={{ border: '1px dashed #d1d5db', borderRadius: 16, padding: 40, textAlign: 'center', color: '#6b7280' }}>
            Объектов пока нет.
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {properties.map((property) => (
              <div key={property.id} style={{ border: '1px solid #e5e7eb', borderRadius: 12, background: '#fff' }}>
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
                    cursor: 'pointer',
                    textAlign: 'left',
                  }}
                >
                  <div>
                    <div style={{ fontWeight: 600 }}>{property.name}</div>
                    {property.address && (
                      <div style={{ fontSize: 12, color: '#9ca3af', marginTop: 4 }}>{property.address}</div>
                    )}
                  </div>
                  <span style={{ fontSize: 13, color: '#6b7280' }}>{expanded === property.id ? 'Скрыть юниты' : 'Юниты'}</span>
                </button>
                {expanded === property.id && (
                  <div style={{ borderTop: '1px solid #f0f0f0', padding: 16 }}>
                    {(units[property.id] ?? []).length === 0 ? (
                      <p style={{ fontSize: 13, color: '#9ca3af', margin: '0 0 12px' }}>Юнитов пока нет.</p>
                    ) : (
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginBottom: 12 }}>
                        {(units[property.id] ?? []).map((unit) => (
                          <span
                            key={unit.id}
                            style={{
                              padding: '4px 10px',
                              borderRadius: 999,
                              background: '#f3f4f6',
                              fontSize: 12,
                              color: '#374151',
                            }}
                          >
                            {unit.unit_number}
                          </span>
                        ))}
                      </div>
                    )}
                    <form onSubmit={(e) => addUnit(property.id, e)} style={{ display: 'flex', gap: 8 }}>
                      <input
                        placeholder="Номер юнита"
                        value={newUnitNumber}
                        onChange={(e) => setNewUnitNumber(e.target.value)}
                        style={{ ...input, flex: 1 }}
                      />
                      <button type="submit" disabled={addingUnit} style={button}>
                        {addingUnit ? '...' : 'Добавить юнит'}
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

export default function PropertiesPage() {
  return (
    <RequireAuth>
      <PropertiesList />
    </RequireAuth>
  );
}
