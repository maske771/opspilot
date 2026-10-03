'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { PropertyImport } from '../components/PropertyImport';
import { RequireAuth, useAuth } from '../lib/auth';
import {
  apiFetch,
  ApiError,
  type ChannelRead,
  type OrganizationRead,
  type PropertyRead,
  type SlaDefault,
  type TicketRead,
  type UserRole,
} from '../lib/api';
import { useLocale } from '../lib/locale';
import { isAdminRole } from '../lib/roles';
import { PRIORITY_KEYS, priorityBadgeStyle } from '../lib/ui';

const STEP_KEYS = ['company', 'channel', 'property', 'team', 'sla', 'test', 'golive'] as const;
type StepKey = (typeof STEP_KEYS)[number];

const INVITE_ROLES: UserRole[] = ['admin', 'manager', 'staff', 'technician'];

function formatMinutes(minutes: number, t: (key: 'onboarding.sla.min' | 'onboarding.sla.hour' | 'onboarding.sla.day') => string): string {
  if (minutes % 1440 === 0) return `${minutes / 1440} ${t('onboarding.sla.day')}`;
  if (minutes % 60 === 0) return `${minutes / 60} ${t('onboarding.sla.hour')}`;
  return `${minutes} ${t('onboarding.sla.min')}`;
}

function StepShell({
  title,
  desc,
  children,
  onBack,
  onContinue,
  onSkip,
  continueLabel,
  continueDisabled,
}: {
  title: string;
  desc: string;
  children: React.ReactNode;
  onBack?: () => void;
  onContinue?: () => void;
  onSkip?: () => void;
  continueLabel: string;
  continueDisabled?: boolean;
}) {
  const { t } = useLocale();
  return (
    <div className="card card-pad" style={{ maxWidth: 560 }}>
      <h2 style={{ fontSize: 17, marginTop: 0, marginBottom: 6 }}>{title}</h2>
      <p style={{ fontSize: 13.5, color: 'var(--color-text-muted)', marginTop: 0, marginBottom: 20 }}>{desc}</p>
      {children}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginTop: 24 }}>
        {onBack && (
          <button type="button" className="btn btn-secondary" onClick={onBack}>
            {t('common.back')}
          </button>
        )}
        <div style={{ flex: 1 }} />
        {onSkip && (
          <button type="button" className="btn btn-secondary" onClick={onSkip}>
            {t('common.skip')}
          </button>
        )}
        {onContinue && (
          <button type="button" className="btn btn-accent" disabled={continueDisabled} onClick={onContinue}>
            {continueLabel}
          </button>
        )}
      </div>
    </div>
  );
}

function OnboardingWizard() {
  const { token, user } = useAuth();
  const { t } = useLocale();
  const router = useRouter();

  const [loadingOrg, setLoadingOrg] = useState(true);
  const [org, setOrg] = useState<OrganizationRead | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [stepIndex, setStepIndex] = useState(0);

  // company
  const [name, setName] = useState('');
  const [savingName, setSavingName] = useState(false);

  // channel
  const [channels, setChannels] = useState<ChannelRead[]>([]);
  const [channelName, setChannelName] = useState('');
  const [accountId, setAccountId] = useState('');
  const [botToken, setBotToken] = useState('');
  const [connecting, setConnecting] = useState(false);
  const channelConnected = channels.some((c) => c.status === 'connected');

  // property
  const [propName, setPropName] = useState('');
  const [propAddress, setPropAddress] = useState('');
  const [addingProperty, setAddingProperty] = useState(false);
  const [propertyAdded, setPropertyAdded] = useState(false);

  // team
  const [inviteEmail, setInviteEmail] = useState('');
  const [invitePassword, setInvitePassword] = useState('');
  const [inviteRole, setInviteRole] = useState<UserRole>('technician');
  const [inviting, setInviting] = useState(false);
  const [invited, setInvited] = useState(false);

  // sla
  const [slaDefaults, setSlaDefaults] = useState<SlaDefault[] | null>(null);

  // test
  const [testStartedAt, setTestStartedAt] = useState<string | null>(null);
  const [testPropertyCode, setTestPropertyCode] = useState<string | null>(null);
  const [checking, setChecking] = useState(false);
  const [testOutcome, setTestOutcome] = useState<'pending' | 'ok' | 'none'>('pending');

  // go live
  const [finishing, setFinishing] = useState(false);

  useEffect(() => {
    if (!token) return;
    Promise.all([apiFetch<OrganizationRead>('/organization', { token }), apiFetch<ChannelRead[]>('/channels', { token })])
      .then(([o, c]) => {
        if (o.onboarding_completed) {
          router.replace('/dashboard');
          return;
        }
        setOrg(o);
        setName(o.name);
        setChannels(c);
      })
      .catch((err) => setError(err instanceof Error ? err.message : t('onboarding.loadFailed')))
      .finally(() => setLoadingOrg(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  useEffect(() => {
    if (STEP_KEYS[stepIndex] === 'sla' && slaDefaults === null && token) {
      apiFetch<SlaDefault[]>('/sla/defaults', { token })
        .then(setSlaDefaults)
        .catch((err) => setError(err instanceof Error ? err.message : t('onboarding.sla.loadFailed')));
    }
    if (STEP_KEYS[stepIndex] === 'test' && testStartedAt === null) {
      setTestStartedAt(new Date().toISOString());
    }
    if (STEP_KEYS[stepIndex] === 'test' && token) {
      // With a property, a new customer is first asked for its code before the request becomes a ticket.
      apiFetch<PropertyRead[]>('/properties', { token })
        .then((list) => setTestPropertyCode(list[0]?.code ?? null))
        .catch(() => undefined);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stepIndex, token]);

  function goTo(key: StepKey) {
    setError(null);
    setStepIndex(STEP_KEYS.indexOf(key));
  }
  function next() {
    setError(null);
    setStepIndex((i) => Math.min(i + 1, STEP_KEYS.length - 1));
  }
  function back() {
    setError(null);
    setStepIndex((i) => Math.max(i - 1, 0));
  }

  async function saveCompany() {
    if (!token) return;
    setSavingName(true);
    setError(null);
    try {
      const updated = await apiFetch<OrganizationRead>('/organization', { method: 'PATCH', token, body: { name } });
      setOrg(updated);
      next();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t('onboarding.company.saveFailed'));
    } finally {
      setSavingName(false);
    }
  }

  async function connectChannel(e: React.FormEvent) {
    e.preventDefault();
    if (!token) return;
    setConnecting(true);
    setError(null);
    try {
      const channel = await apiFetch<ChannelRead>('/channels/telegram/connect', {
        method: 'POST',
        token,
        body: { name: channelName, account_id: accountId, credentials: { bot_token: botToken } },
      });
      setChannels((prev) => [...prev, channel]);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t('onboarding.channel.connectFailed'));
    } finally {
      setConnecting(false);
    }
  }

  async function addProperty(e: React.FormEvent) {
    e.preventDefault();
    if (!token || !user) return;
    setAddingProperty(true);
    setError(null);
    try {
      await apiFetch('/properties', {
        method: 'POST',
        token,
        body: { organization_id: user.organization_id, name: propName, address: propAddress || null },
      });
      setPropertyAdded(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t('onboarding.property.addFailed'));
    } finally {
      setAddingProperty(false);
    }
  }

  async function inviteTeammate(e: React.FormEvent) {
    e.preventDefault();
    if (!token) return;
    setInviting(true);
    setError(null);
    try {
      await apiFetch('/users', { method: 'POST', token, body: { email: inviteEmail, password: invitePassword, role: inviteRole } });
      setInvited(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t('onboarding.team.inviteFailed'));
    } finally {
      setInviting(false);
    }
  }

  async function checkForTestTicket() {
    if (!token || !testStartedAt) return;
    setChecking(true);
    setError(null);
    try {
      const tickets = await apiFetch<TicketRead[]>('/tickets?limit=1', { token });
      const found = tickets.length > 0 && tickets[0].created_at >= testStartedAt;
      setTestOutcome(found ? 'ok' : 'none');
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t('onboarding.test.checkFailed'));
    } finally {
      setChecking(false);
    }
  }

  async function finish() {
    if (!token) return;
    setFinishing(true);
    setError(null);
    try {
      await apiFetch('/organization', { method: 'PATCH', token, body: { onboarding_completed: true } });
      router.push('/dashboard');
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t('onboarding.golive.finishFailed'));
      setFinishing(false);
    }
  }

  if (loadingOrg || !org) {
    return (
      <main className="page">
        <p style={{ color: 'var(--color-text-muted)' }}>{t('common.loading')}</p>
      </main>
    );
  }

  const step = STEP_KEYS[stepIndex];

  return (
    <main className="page">
      <h1 className="page-title">{t('onboarding.title')}</h1>
      <p className="page-subtitle">{t('onboarding.subtitle')}</p>
      <p style={{ fontSize: 12.5, color: 'var(--color-text-subtle)', marginBottom: 20 }}>
        {t('onboarding.stepLabel', { current: stepIndex + 1, total: STEP_KEYS.length })}
      </p>

      {error && (
        <div style={{ padding: 12, borderRadius: 10, background: 'var(--color-danger-soft)', color: 'var(--color-danger)', marginBottom: 20, maxWidth: 560 }}>
          {error}
        </div>
      )}

      {step === 'company' && (
        <StepShell
          title={t('onboarding.company.title')}
          desc={t('onboarding.company.desc')}
          onContinue={saveCompany}
          continueLabel={savingName ? t('common.saving') : t('common.continue')}
          continueDisabled={savingName || !name.trim()}
        >
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder={t('onboarding.company.namePlaceholder')}
            className="input"
            style={{ width: '100%' }}
          />
        </StepShell>
      )}

      {step === 'channel' && (
        <StepShell
          title={t('onboarding.channel.title')}
          desc={t('onboarding.channel.desc')}
          onBack={back}
          onSkip={channelConnected ? undefined : next}
          onContinue={channelConnected ? next : undefined}
          continueLabel={t('common.continue')}
        >
          {channelConnected ? (
            <div style={{ padding: 12, borderRadius: 10, background: 'var(--status-completed-bg)', color: 'var(--status-completed-text)', fontSize: 13 }}>
              {t('onboarding.channel.connected')}
            </div>
          ) : (
            <form onSubmit={connectChannel} style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              <input
                required
                value={channelName}
                onChange={(e) => setChannelName(e.target.value)}
                placeholder={t('onboarding.channel.namePlaceholder')}
                className="input"
              />
              <input
                required
                value={accountId}
                onChange={(e) => setAccountId(e.target.value)}
                placeholder={t('onboarding.channel.accountIdPlaceholder')}
                className="input"
              />
              <input
                required
                type="password"
                autoComplete="new-password"
                value={botToken}
                onChange={(e) => setBotToken(e.target.value)}
                placeholder={t('field.botToken')}
                className="input"
              />
              <button type="submit" disabled={connecting} className="btn btn-accent" style={{ alignSelf: 'flex-start' }}>
                {connecting ? t('onboarding.channel.connecting') : t('onboarding.channel.connect')}
              </button>
            </form>
          )}
        </StepShell>
      )}

      {step === 'property' && (
        <StepShell
          title={t('onboarding.property.title')}
          desc={t('onboarding.property.desc')}
          onBack={back}
          onSkip={propertyAdded ? undefined : next}
          onContinue={propertyAdded ? next : undefined}
          continueLabel={t('common.continue')}
        >
          {propertyAdded ? (
            <div style={{ padding: 12, borderRadius: 10, background: 'var(--status-completed-bg)', color: 'var(--status-completed-text)', fontSize: 13 }}>
              {t('onboarding.property.added')}
            </div>
          ) : (
            <form onSubmit={addProperty} style={{ display: 'flex', gap: 10 }}>
              <input
                required
                value={propName}
                onChange={(e) => setPropName(e.target.value)}
                placeholder={t('properties.namePlaceholder')}
                className="input"
                style={{ flex: 1 }}
              />
              <input
                value={propAddress}
                onChange={(e) => setPropAddress(e.target.value)}
                placeholder={t('properties.addressPlaceholder')}
                className="input"
                style={{ flex: 1 }}
              />
              <button type="submit" disabled={addingProperty} className="btn btn-accent">
                {addingProperty ? t('common.adding') : t('common.add')}
              </button>
            </form>
          )}
          {!propertyAdded && (
            <div style={{ marginTop: 14 }}>
              <PropertyImport onImported={() => setPropertyAdded(true)} />
            </div>
          )}
        </StepShell>
      )}

      {step === 'team' && (
        <StepShell
          title={t('onboarding.team.title')}
          desc={t('onboarding.team.desc')}
          onBack={back}
          onSkip={invited ? undefined : next}
          onContinue={invited ? next : undefined}
          continueLabel={t('common.continue')}
        >
          {invited ? (
            <div style={{ padding: 12, borderRadius: 10, background: 'var(--status-completed-bg)', color: 'var(--status-completed-text)', fontSize: 13 }}>
              {t('onboarding.team.invited')}
            </div>
          ) : (
            <form onSubmit={inviteTeammate} style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              <input required type="email" value={inviteEmail} onChange={(e) => setInviteEmail(e.target.value)} placeholder={t('auth.email')} className="input" />
              <input
                required
                type="password"
                minLength={8}
                autoComplete="new-password"
                value={invitePassword}
                onChange={(e) => setInvitePassword(e.target.value)}
                placeholder={t('auth.password')}
                className="input"
              />
              <select value={inviteRole} onChange={(e) => setInviteRole(e.target.value as UserRole)} className="select">
                {INVITE_ROLES.map((r) => (
                  <option key={r} value={r}>
                    {r}
                  </option>
                ))}
              </select>
              <button type="submit" disabled={inviting} className="btn btn-accent" style={{ alignSelf: 'flex-start' }}>
                {inviting ? t('onboarding.team.inviting') : t('onboarding.team.invite')}
              </button>
            </form>
          )}
        </StepShell>
      )}

      {step === 'sla' && (
        <StepShell title={t('onboarding.sla.title')} desc={t('onboarding.sla.desc')} onBack={back} onContinue={next} continueLabel={t('common.continue')}>
          {!slaDefaults ? (
            <p style={{ color: 'var(--color-text-muted)' }}>{t('common.loading')}</p>
          ) : (
            <div>
              {slaDefaults.map((row) => (
                <div key={row.priority} style={{ display: 'flex', alignItems: 'center', gap: 14, padding: '8px 0', borderBottom: '1px solid var(--color-border-subtle)' }}>
                  <span className="badge" style={{ ...priorityBadgeStyle(row.priority), minWidth: 70, textAlign: 'center' }}>
                    {t(PRIORITY_KEYS[row.priority])}
                  </span>
                  <span style={{ fontSize: 13, color: 'var(--color-text-muted)' }}>
                    {t('onboarding.sla.response')}: <strong>{formatMinutes(row.response_minutes, t)}</strong>
                  </span>
                  <span style={{ fontSize: 13, color: 'var(--color-text-muted)' }}>
                    {t('onboarding.sla.resolution')}: <strong>{formatMinutes(row.resolution_minutes, t)}</strong>
                  </span>
                </div>
              ))}
            </div>
          )}
        </StepShell>
      )}

      {step === 'test' && (
        <StepShell
          title={t('onboarding.test.title')}
          desc={channelConnected ? t('onboarding.test.desc') : t('onboarding.test.noChannel')}
          onBack={back}
          onContinue={next}
          continueLabel={t('common.continue')}
        >
          {channelConnected && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              {testPropertyCode && (
                <div style={{ padding: 12, borderRadius: 10, background: 'var(--color-accent-soft)', color: 'var(--color-accent-text)', fontSize: 13 }}>
                  {t('onboarding.test.codeHint', { code: testPropertyCode })}
                </div>
              )}
              <button type="button" className="btn btn-secondary" style={{ alignSelf: 'flex-start' }} disabled={checking} onClick={checkForTestTicket}>
                {checking ? t('onboarding.test.checking') : t('onboarding.test.check')}
              </button>
              {testOutcome === 'ok' && (
                <div style={{ padding: 12, borderRadius: 10, background: 'var(--status-completed-bg)', color: 'var(--status-completed-text)', fontSize: 13 }}>
                  {t('onboarding.test.success')}
                </div>
              )}
              {testOutcome === 'none' && (
                <div style={{ padding: 12, borderRadius: 10, background: 'var(--color-bg)', color: 'var(--color-text-muted)', fontSize: 13 }}>
                  {t('onboarding.test.notYet')}
                </div>
              )}
            </div>
          )}
        </StepShell>
      )}

      {step === 'golive' && (
        <StepShell title={t('onboarding.golive.title')} desc={t('onboarding.golive.desc')} onBack={back} onContinue={finish} continueLabel={finishing ? t('common.saving') : t('onboarding.golive.finish')} continueDisabled={finishing}>
          <ul style={{ margin: 0, paddingLeft: 20, display: 'flex', flexDirection: 'column', gap: 8, fontSize: 13.5 }}>
            <li>{t('onboarding.golive.company', { name: org.name })}</li>
            <li>{channelConnected ? t('onboarding.golive.channelDone') : t('onboarding.golive.channelSkipped')}</li>
            <li>{propertyAdded ? t('onboarding.golive.propertyDone') : t('onboarding.golive.propertySkipped')}</li>
            <li>{invited ? t('onboarding.golive.teamDone') : t('onboarding.golive.teamSkipped')}</li>
          </ul>
        </StepShell>
      )}

      <div style={{ display: 'flex', gap: 6, marginTop: 24 }}>
        {STEP_KEYS.map((key, i) => (
          <button
            key={key}
            type="button"
            onClick={() => goTo(key)}
            aria-label={key}
            style={{
              width: 8,
              height: 8,
              borderRadius: 999,
              border: 'none',
              padding: 0,
              cursor: 'pointer',
              background: i === stepIndex ? 'var(--color-accent)' : 'var(--color-border)',
            }}
          />
        ))}
      </div>
    </main>
  );
}

function OnboardingPage() {
  const { user } = useAuth();
  const { t } = useLocale();

  if (!isAdminRole(user?.role)) {
    return (
      <main className="page">
        <div className="empty-state">{t('common.ownerAdminOnly')}</div>
      </main>
    );
  }

  return <OnboardingWizard />;
}

export default function Onboarding() {
  return (
    <RequireAuth>
      <OnboardingPage />
    </RequireAuth>
  );
}
