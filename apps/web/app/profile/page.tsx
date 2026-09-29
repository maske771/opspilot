'use client';

import { useCallback, useEffect, useState } from 'react';
import { RequireAuth, useAuth } from '../lib/auth';
import { apiFetch, ApiError, type TelegramLinkCode, type TelegramStatus } from '../lib/api';
import { useLocale } from '../lib/locale';

function ProfilePage() {
  const { token, user } = useAuth();
  const { t, tOr, formatDateTime } = useLocale();
  const [status, setStatus] = useState<TelegramStatus | null>(null);
  const [code, setCode] = useState<TelegramLinkCode | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [copied, setCopied] = useState(false);

  const load = useCallback(() => {
    if (!token) return;
    apiFetch<TelegramStatus>('/me/telegram', { token })
      .then(setStatus)
      .catch((err) => setError(err instanceof Error ? err.message : t('profile.loadFailed')));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  useEffect(() => {
    load();
  }, [load]);

  // While a code is on screen, watch for the employee finishing the link in Telegram.
  useEffect(() => {
    if (!code || status?.linked) return;
    const timer = setInterval(load, 3000);
    return () => clearInterval(timer);
  }, [code, status?.linked, load]);

  useEffect(() => {
    if (status?.linked) setCode(null);
  }, [status?.linked]);

  async function generateCode() {
    if (!token) return;
    setBusy(true);
    setError(null);
    try {
      setCode(await apiFetch<TelegramLinkCode>('/me/telegram-link-code', { method: 'POST', token }));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t('profile.codeFailed'));
    } finally {
      setBusy(false);
    }
  }

  async function unlink() {
    if (!token || !window.confirm(t('profile.unlinkConfirm'))) return;
    setBusy(true);
    setError(null);
    try {
      await apiFetch('/me/telegram-link', { method: 'DELETE', token });
      setStatus((prev) => (prev ? { ...prev, linked: false } : prev));
      setCode(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t('profile.unlinkFailed'));
    } finally {
      setBusy(false);
    }
  }

  async function copyCommand() {
    if (!code) return;
    try {
      await navigator.clipboard.writeText(`/link ${code.code}`);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* the command is on screen, the user can select it */
    }
  }

  return (
    <main className="page-narrow">
      <h1 className="page-title">{t('profile.title')}</h1>
      <p className="page-subtitle">{t('profile.subtitle')}</p>

      {error && (
        <div style={{ padding: 14, borderRadius: 10, background: 'var(--color-danger-soft)', color: 'var(--color-danger)', marginBottom: 20 }}>
          {error}
        </div>
      )}

      <section className="card card-pad" style={{ marginBottom: 16 }}>
        <div style={{ fontWeight: 600, fontSize: 14, marginBottom: 12 }}>{t('profile.account')}</div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{ fontSize: 14 }}>{user?.email}</span>
          {user && (
            <span className="badge" style={{ background: 'var(--color-bg)', color: 'var(--color-text-muted)' }}>
              {tOr(`role.${user.role}`, user.role)}
            </span>
          )}
        </div>
      </section>

      <section className="card card-pad">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
          <div style={{ fontWeight: 600, fontSize: 14 }}>{t('profile.telegramTitle')}</div>
          {status && (
            <span
              className="badge"
              style={{
                background: status.linked ? 'var(--status-completed-bg)' : 'var(--status-closed-bg)',
                color: status.linked ? 'var(--status-completed-text)' : 'var(--status-closed-text)',
              }}
            >
              {status.linked ? t('profile.linked') : t('profile.notLinked')}
            </span>
          )}
        </div>
        <p style={{ margin: '0 0 14px', fontSize: 13, color: 'var(--color-text-muted)' }}>{t('profile.telegramHelp')}</p>

        {status && !status.linked && !status.channel_available && (
          <div className="empty-state" style={{ padding: 20 }}>{t('profile.noBot')}</div>
        )}

        {status && !status.linked && status.channel_available && !code && (
          <button type="button" className="btn btn-accent" disabled={busy} onClick={generateCode}>
            {t('profile.getCode')}
          </button>
        )}

        {status && !status.linked && code && (
          <div>
            {code.deep_link && (
              <a href={code.deep_link} target="_blank" rel="noreferrer" className="btn btn-accent" style={{ textDecoration: 'none', marginBottom: 14 }}>
                {t('profile.openTelegram')}
              </a>
            )}
            <div style={{ fontSize: 13, color: 'var(--color-text-muted)', marginBottom: 8 }}>{t('profile.orSend')}</div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10 }}>
              <code style={{ fontSize: 18, fontWeight: 700, letterSpacing: '0.08em', padding: '8px 14px', borderRadius: 'var(--radius-sm)', background: 'var(--color-bg)', border: '1px solid var(--color-border)' }}>
                /link {code.code}
              </code>
              <button type="button" className="btn btn-secondary" onClick={copyCommand}>
                {copied ? t('common.copied') : t('common.copy')}
              </button>
            </div>
            <div style={{ fontSize: 12, color: 'var(--color-text-subtle)' }}>
              {t('profile.codeValidUntil', { time: formatDateTime(code.expires_at) })}
            </div>
          </div>
        )}

        {status?.linked && (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
            <span style={{ fontSize: 13, color: 'var(--color-text-muted)' }}>{t('profile.linkedNote')}</span>
            <button type="button" className="btn btn-secondary" disabled={busy} onClick={unlink}>
              {t('profile.unlink')}
            </button>
          </div>
        )}
      </section>
    </main>
  );
}

export default function Profile() {
  return (
    <RequireAuth>
      <ProfilePage />
    </RequireAuth>
  );
}
