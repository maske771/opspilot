'use client';

import { useCallback, useEffect, useState } from 'react';
import { Nav } from '../components/Nav';
import { RequireAuth, useAuth } from '../lib/auth';
import { API_BASE, apiFetch, ApiError, type ChannelRead, type ChannelType } from '../lib/api';
import { isAdminRole } from '../lib/roles';

type FieldDef = { key: string; label: string; secret?: boolean; optional?: boolean; placeholder?: string };

const CHANNEL_DEFS: Record<ChannelType, { label: string; verified: boolean; fields: FieldDef[] }> = {
  telegram: {
    label: 'Telegram',
    verified: true,
    fields: [{ key: 'bot_token', label: 'Bot token', secret: true, placeholder: '123456:ABC-DEF...' }],
  },
  line: {
    label: 'LINE',
    verified: false,
    fields: [{ key: 'channel_access_token', label: 'Channel access token', secret: true }],
  },
  whatsapp: {
    label: 'WhatsApp',
    verified: false,
    fields: [
      { key: 'access_token', label: 'Access token', secret: true },
      { key: 'phone_number_id', label: 'Phone number ID' },
    ],
  },
  email: {
    label: 'Email',
    verified: false,
    fields: [
      { key: 'smtp_host', label: 'SMTP host', placeholder: 'smtp.example.com' },
      { key: 'smtp_port', label: 'SMTP port', optional: true, placeholder: '587' },
      { key: 'smtp_username', label: 'SMTP логин', optional: true },
      { key: 'smtp_password', label: 'SMTP пароль', secret: true, optional: true },
      { key: 'from_address', label: 'Адрес отправителя', placeholder: 'support@example.com' },
    ],
  },
};

const CHANNEL_TYPES = Object.keys(CHANNEL_DEFS) as ChannelType[];

function compact(values: Record<string, string>): Record<string, string> {
  return Object.fromEntries(
    Object.entries(values)
      .map(([key, value]): [string, string] => [key, value.trim()])
      .filter(([, value]) => value !== ''),
  );
}

function webhookUrl(channel: ChannelRead): string {
  return `${API_BASE}/webhooks/${channel.type}/${encodeURIComponent(channel.account_id)}`;
}

function CredentialInputs({
  type,
  values,
  onChange,
}: {
  type: ChannelType;
  values: Record<string, string>;
  onChange: (next: Record<string, string>) => void;
}) {
  return (
    <>
      {CHANNEL_DEFS[type].fields.map((field) => (
        <input
          key={field.key}
          required={!field.optional}
          type={field.secret ? 'password' : 'text'}
          autoComplete={field.secret ? 'new-password' : 'off'}
          placeholder={field.optional ? `${field.label} (необязательно)` : field.label}
          title={field.placeholder ? `${field.label}, например ${field.placeholder}` : field.label}
          value={values[field.key] ?? ''}
          onChange={(e) => onChange({ ...values, [field.key]: e.target.value })}
          className="input"
          style={{ flex: '1 1 220px' }}
        />
      ))}
    </>
  );
}

function ChannelsPage() {
  const { token, user } = useAuth();
  const [channels, setChannels] = useState<ChannelRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [type, setType] = useState<ChannelType>('telegram');
  const [name, setName] = useState('');
  const [accountId, setAccountId] = useState('');
  const [credentials, setCredentials] = useState<Record<string, string>>({});
  const [connecting, setConnecting] = useState(false);

  const [busyId, setBusyId] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editCredentials, setEditCredentials] = useState<Record<string, string>>({});
  const [copiedId, setCopiedId] = useState<string | null>(null);

  const load = useCallback(() => {
    if (!token) return;
    setLoading(true);
    apiFetch<ChannelRead[]>('/channels', { token })
      .then(setChannels)
      .catch((err) => setError(err instanceof Error ? err.message : 'Не удалось загрузить каналы'))
      .finally(() => setLoading(false));
  }, [token]);

  useEffect(() => {
    load();
  }, [load]);

  function changeType(next: ChannelType) {
    setType(next);
    setCredentials({});
  }

  async function connect(e: React.FormEvent) {
    e.preventDefault();
    if (!token) return;
    setConnecting(true);
    setError(null);
    const creds = compact(credentials);
    try {
      await apiFetch(`/channels/${type}/connect`, {
        method: 'POST',
        token,
        body: {
          account_id: accountId.trim(),
          name: name.trim(),
          credentials: Object.keys(creds).length > 0 ? creds : null,
        },
      });
      setName('');
      setAccountId('');
      setCredentials({});
      load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось подключить канал');
    } finally {
      setConnecting(false);
    }
  }

  async function patchChannel(channel: ChannelRead, body: Record<string, unknown>, failure: string): Promise<boolean> {
    if (!token) return false;
    setBusyId(channel.id);
    setError(null);
    try {
      const updated = await apiFetch<ChannelRead>(`/channels/${channel.id}`, { method: 'PATCH', token, body });
      setChannels((prev) => prev.map((c) => (c.id === updated.id ? updated : c)));
      return true;
    } catch (err) {
      setError(err instanceof ApiError ? err.message : failure);
      return false;
    } finally {
      setBusyId(null);
    }
  }

  async function saveCredentials(channel: ChannelRead, e: React.FormEvent) {
    e.preventDefault();
    const ok = await patchChannel(channel, { credentials: compact(editCredentials) }, 'Не удалось обновить доступы');
    if (ok) {
      setEditingId(null);
      setEditCredentials({});
    }
  }

  async function copyWebhook(channel: ChannelRead) {
    try {
      await navigator.clipboard.writeText(webhookUrl(channel));
      setCopiedId(channel.id);
      setTimeout(() => setCopiedId((current) => (current === channel.id ? null : current)), 1500);
    } catch {
      setError('Не удалось скопировать — выделите URL вручную');
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

  const sorted = [...channels].sort((a, b) => Number(b.status === 'connected') - Number(a.status === 'connected'));
  const def = CHANNEL_DEFS[type];

  return (
    <>
      <Nav />
      <main className="page">
        <h1 className="page-title">Channels</h1>
        <p className="page-subtitle">
          Каналы, через которые клиенты пишут в OpsPilot. После подключения укажите URL вебхука в настройках провайдера.
        </p>

        <form onSubmit={connect} className="card card-pad" style={{ marginBottom: 24 }}>
          <div style={{ fontWeight: 600, fontSize: 14, marginBottom: 12 }}>Подключить канал</div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10 }}>
            <select value={type} onChange={(e) => changeType(e.target.value as ChannelType)} className="input" style={{ flex: '0 0 150px' }}>
              {CHANNEL_TYPES.map((t) => (
                <option key={t} value={t}>
                  {CHANNEL_DEFS[t].label}
                </option>
              ))}
            </select>
            <input
              required
              placeholder="Название (для команды)"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="input"
              style={{ flex: '1 1 220px' }}
            />
            <input
              required
              placeholder="Account ID"
              title="Произвольный идентификатор канала. Входит в URL вебхука."
              value={accountId}
              onChange={(e) => setAccountId(e.target.value)}
              className="input"
              style={{ flex: '1 1 220px' }}
            />
            <CredentialInputs type={type} values={credentials} onChange={setCredentials} />
          </div>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, marginTop: 12 }}>
            <span style={{ fontSize: 12, color: 'var(--color-text-subtle)' }}>
              Account ID — произвольный идентификатор (например, имя бота или адрес ящика); он входит в URL вебхука.
              {!def.verified && ' Интеграция с этим каналом ещё не проверялась на реальном аккаунте.'}
            </span>
            <button type="submit" disabled={connecting} className="btn btn-accent" style={{ flexShrink: 0 }}>
              {connecting ? 'Подключение...' : 'Подключить'}
            </button>
          </div>
        </form>

        {error && (
          <div style={{ padding: 14, borderRadius: 10, background: 'var(--color-danger-soft)', color: 'var(--color-danger)', marginBottom: 20 }}>
            {error}
          </div>
        )}

        {loading ? (
          <p style={{ color: 'var(--color-text-muted)' }}>Загрузка...</p>
        ) : sorted.length === 0 ? (
          <div className="empty-state">Каналов пока нет. Подключите первый выше.</div>
        ) : (
          <div className="card">
            {sorted.map((channel) => {
              const connected = channel.status === 'connected';
              const busy = busyId === channel.id;
              return (
                <div key={channel.id} className="list-row" style={{ opacity: connected ? 1 : 0.7 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10, minWidth: 0 }}>
                      <span style={{ fontWeight: 600, fontSize: 14 }}>{channel.name}</span>
                      <span className="badge" style={{ background: 'var(--color-accent-soft)', color: 'var(--color-accent-text)' }}>
                        {CHANNEL_DEFS[channel.type]?.label ?? channel.type}
                      </span>
                      <span
                        className="badge"
                        style={{
                          background: connected ? 'var(--status-completed-bg)' : 'var(--status-closed-bg)',
                          color: connected ? 'var(--status-completed-text)' : 'var(--status-closed-text)',
                        }}
                      >
                        {connected ? 'Подключён' : 'Отключён'}
                      </span>
                      {!channel.has_credentials && (
                        <span className="badge" style={{ background: 'var(--priority-high-bg)', color: 'var(--priority-high-text)' }}>
                          Нет доступов — бот не сможет отвечать
                        </span>
                      )}
                    </div>
                    <div style={{ display: 'flex', gap: 6, flexShrink: 0 }}>
                      <button
                        type="button"
                        className="btn btn-ghost"
                        disabled={busy}
                        onClick={() => {
                          setEditCredentials({});
                          setEditingId(editingId === channel.id ? null : channel.id);
                        }}
                      >
                        Обновить доступы
                      </button>
                      <button
                        type="button"
                        className="btn btn-secondary"
                        disabled={busy}
                        onClick={() =>
                          patchChannel(
                            channel,
                            { status: connected ? 'disconnected' : 'connected' },
                            connected ? 'Не удалось отключить канал' : 'Не удалось подключить канал',
                          )
                        }
                      >
                        {connected ? 'Отключить' : 'Подключить снова'}
                      </button>
                    </div>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 8, fontSize: 12, color: 'var(--color-text-muted)' }}>
                    <span style={{ flexShrink: 0 }}>Webhook:</span>
                    <code style={{ overflowWrap: 'anywhere' }}>{webhookUrl(channel)}</code>
                    <button type="button" className="btn btn-ghost" style={{ flexShrink: 0 }} onClick={() => copyWebhook(channel)}>
                      {copiedId === channel.id ? 'Скопировано' : 'Копировать'}
                    </button>
                  </div>

                  {editingId === channel.id && (
                    <form onSubmit={(e) => saveCredentials(channel, e)} style={{ marginTop: 12 }}>
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10 }}>
                        <CredentialInputs type={channel.type} values={editCredentials} onChange={setEditCredentials} />
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginTop: 10 }}>
                        <button type="submit" disabled={busy} className="btn btn-accent">
                          {busy ? 'Сохранение...' : 'Сохранить'}
                        </button>
                        <button type="button" className="btn btn-ghost" onClick={() => setEditingId(null)}>
                          Отмена
                        </button>
                        <span style={{ fontSize: 12, color: 'var(--color-text-subtle)' }}>
                          Текущие значения скрыты — введите все поля заново, они заменят старые.
                        </span>
                      </div>
                    </form>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </main>
    </>
  );
}

export default function Channels() {
  return (
    <RequireAuth>
      <ChannelsPage />
    </RequireAuth>
  );
}
