'use client';

import { useCallback, useEffect, useState } from 'react';
import { RequireAuth, useAuth } from '../lib/auth';
import { API_BASE, apiFetch, ApiError, type ChannelRead, type ChannelType } from '../lib/api';
import type { MessageKey } from '../lib/i18n/en';
import { useLocale } from '../lib/locale';
import { isAdminRole } from '../lib/roles';

type FieldDef = { key: string; label: MessageKey; secret?: boolean; optional?: boolean; example?: string };

const CHANNEL_DEFS: Record<ChannelType, { label: string; verified: boolean; fields: FieldDef[] }> = {
  telegram: {
    label: 'Telegram',
    verified: true,
    fields: [{ key: 'bot_token', label: 'field.botToken', secret: true, example: '123456:ABC-DEF...' }],
  },
  line: {
    label: 'LINE',
    verified: false,
    fields: [{ key: 'channel_access_token', label: 'field.channelAccessToken', secret: true }],
  },
  whatsapp: {
    label: 'WhatsApp',
    verified: false,
    fields: [
      { key: 'access_token', label: 'field.accessToken', secret: true },
      { key: 'phone_number_id', label: 'field.phoneNumberId' },
    ],
  },
  email: {
    label: 'Email',
    verified: false,
    fields: [
      { key: 'smtp_host', label: 'field.smtpHost', example: 'smtp.example.com' },
      { key: 'smtp_port', label: 'field.smtpPort', optional: true, example: '587' },
      { key: 'smtp_username', label: 'field.smtpUsername', optional: true },
      { key: 'smtp_password', label: 'field.smtpPassword', secret: true, optional: true },
      { key: 'from_address', label: 'field.fromAddress', example: 'support@example.com' },
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

function webhookBase(channel: ChannelRead): string {
  return `${API_BASE}/webhooks/${channel.type}/${encodeURIComponent(channel.account_id)}`;
}

function webhookUrl(channel: ChannelRead): string {
  return channel.webhook_token ? `${webhookBase(channel)}?token=${encodeURIComponent(channel.webhook_token)}` : webhookBase(channel);
}

// The token is a credential: keep it out of screenshots and shoulder-surfing; "Copy" still copies the full URL.
function maskedWebhookUrl(channel: ChannelRead): string {
  return channel.webhook_token ? `${webhookBase(channel)}?token=••••••••` : webhookBase(channel);
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
  const { t } = useLocale();
  return (
    <>
      {CHANNEL_DEFS[type].fields.map((field) => {
        const label = t(field.label);
        return (
          <input
            key={field.key}
            required={!field.optional}
            type={field.secret ? 'password' : 'text'}
            autoComplete={field.secret ? 'new-password' : 'off'}
            placeholder={field.optional ? `${label} (${t('common.optional')})` : label}
            title={field.example ? `${label}, e.g. ${field.example}` : label}
            value={values[field.key] ?? ''}
            onChange={(e) => onChange({ ...values, [field.key]: e.target.value })}
            className="input"
            style={{ flex: '1 1 220px' }}
          />
        );
      })}
    </>
  );
}

function ChannelsPage() {
  const { token, user } = useAuth();
  const { t } = useLocale();
  const [channels, setChannels] = useState<ChannelRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

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
      .catch((err) => setError(err instanceof Error ? err.message : t('channels.loadFailed')))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
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
      setError(err instanceof ApiError ? err.message : t('channels.connectFailed'));
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
    const ok = await patchChannel(channel, { credentials: compact(editCredentials) }, t('channels.credentialsFailed'));
    if (ok) {
      setEditingId(null);
      setEditCredentials({});
    }
  }

  async function rotateToken(channel: ChannelRead) {
    if (!token || !window.confirm(t('channels.rotateConfirm'))) return;
    setBusyId(channel.id);
    setError(null);
    setNotice(null);
    try {
      const updated = await apiFetch<ChannelRead>(`/channels/${channel.id}/rotate-webhook-token`, { method: 'POST', token });
      setChannels((prev) => prev.map((c) => (c.id === updated.id ? updated : c)));
      setNotice(t('channels.rotated'));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t('channels.rotateFailed'));
    } finally {
      setBusyId(null);
    }
  }

  async function registerWebhook(channel: ChannelRead) {
    if (!token) return;
    setBusyId(channel.id);
    setError(null);
    setNotice(null);
    try {
      await apiFetch(`/channels/${channel.id}/register-webhook`, { method: 'POST', token });
      setNotice(t('channels.webhookRegistered'));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t('channels.registerFailed'));
    } finally {
      setBusyId(null);
    }
  }

  async function copyWebhook(channel: ChannelRead) {
    try {
      await navigator.clipboard.writeText(webhookUrl(channel));
      setCopiedId(channel.id);
      setTimeout(() => setCopiedId((current) => (current === channel.id ? null : current)), 1500);
    } catch {
      setError(t('channels.copyFailed'));
    }
  }

  if (!isAdminRole(user?.role)) {
    return (
      <>
        <main className="page">
          <div className="empty-state">{t('common.ownerAdminOnly')}</div>
        </main>
      </>
    );
  }

  const sorted = [...channels].sort((a, b) => Number(b.status === 'connected') - Number(a.status === 'connected'));
  const def = CHANNEL_DEFS[type];

  return (
    <>
      <main className="page">
        <h1 className="page-title">{t('nav.channels')}</h1>
        <p className="page-subtitle">{t('channels.subtitle')}</p>

        <form onSubmit={connect} className="card card-pad" style={{ marginBottom: 24 }}>
          <div style={{ fontWeight: 600, fontSize: 14, marginBottom: 12 }}>{t('channels.connectTitle')}</div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10 }}>
            <select value={type} onChange={(e) => changeType(e.target.value as ChannelType)} className="input" style={{ flex: '0 0 150px' }}>
              {CHANNEL_TYPES.map((ct) => (
                <option key={ct} value={ct}>
                  {CHANNEL_DEFS[ct].label}
                </option>
              ))}
            </select>
            <input
              required
              placeholder={t('channels.namePlaceholder')}
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="input"
              style={{ flex: '1 1 220px' }}
            />
            <input
              required
              placeholder={t('channels.accountId')}
              title={t('channels.accountIdHint')}
              value={accountId}
              onChange={(e) => setAccountId(e.target.value)}
              className="input"
              style={{ flex: '1 1 220px' }}
            />
            <CredentialInputs type={type} values={credentials} onChange={setCredentials} />
          </div>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, marginTop: 12 }}>
            <span style={{ fontSize: 12, color: 'var(--color-text-subtle)' }}>
              {t('channels.accountIdHelp')}
              {!def.verified && t('channels.notVerified')}
            </span>
            <button type="submit" disabled={connecting} className="btn btn-accent" style={{ flexShrink: 0 }}>
              {connecting ? t('channels.connecting') : t('channels.connect')}
            </button>
          </div>
        </form>

        {error && (
          <div style={{ padding: 14, borderRadius: 10, background: 'var(--color-danger-soft)', color: 'var(--color-danger)', marginBottom: 20 }}>
            {error}
          </div>
        )}

        {notice && (
          <div style={{ padding: 14, borderRadius: 10, background: 'var(--status-completed-bg)', color: 'var(--status-completed-text)', marginBottom: 20 }}>
            {notice}
          </div>
        )}

        {loading ? (
          <p style={{ color: 'var(--color-text-muted)' }}>{t('common.loading')}</p>
        ) : sorted.length === 0 ? (
          <div className="empty-state">{t('channels.empty')}</div>
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
                        {connected ? t('channels.connected') : t('channels.disconnected')}
                      </span>
                      {!channel.has_credentials && (
                        <span className="badge" style={{ background: 'var(--priority-high-bg)', color: 'var(--priority-high-text)' }}>
                          {t('channels.noCredentials')}
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
                        {t('channels.updateCredentials')}
                      </button>
                      <button
                        type="button"
                        className="btn btn-secondary"
                        disabled={busy}
                        onClick={() =>
                          patchChannel(
                            channel,
                            { status: connected ? 'disconnected' : 'connected' },
                            connected ? t('channels.disconnectFailed') : t('channels.reconnectFailed'),
                          )
                        }
                      >
                        {connected ? t('channels.disconnect') : t('channels.reconnect')}
                      </button>
                    </div>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 8, fontSize: 12, color: 'var(--color-text-muted)' }}>
                    <span style={{ flexShrink: 0 }}>{t('channels.webhook')}</span>
                    <code style={{ overflowWrap: 'anywhere' }}>{maskedWebhookUrl(channel)}</code>
                    <button type="button" className="btn btn-ghost" style={{ flexShrink: 0 }} onClick={() => copyWebhook(channel)}>
                      {copiedId === channel.id ? t('common.copied') : t('common.copy')}
                    </button>
                    <button type="button" className="btn btn-ghost" style={{ flexShrink: 0 }} disabled={busy} onClick={() => rotateToken(channel)}>
                      {t('channels.rotateToken')}
                    </button>
                    {channel.type === 'telegram' && (
                      <button type="button" className="btn btn-ghost" style={{ flexShrink: 0 }} disabled={busy} onClick={() => registerWebhook(channel)}>
                        {t('channels.registerWebhook')}
                      </button>
                    )}
                  </div>

                  {editingId === channel.id && (
                    <form onSubmit={(e) => saveCredentials(channel, e)} style={{ marginTop: 12 }}>
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10 }}>
                        <CredentialInputs type={channel.type} values={editCredentials} onChange={setEditCredentials} />
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginTop: 10 }}>
                        <button type="submit" disabled={busy} className="btn btn-accent">
                          {busy ? t('common.saving') : t('common.save')}
                        </button>
                        <button type="button" className="btn btn-ghost" onClick={() => setEditingId(null)}>
                          {t('common.cancel')}
                        </button>
                        <span style={{ fontSize: 12, color: 'var(--color-text-subtle)' }}>{t('channels.credentialsHelp')}</span>
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
