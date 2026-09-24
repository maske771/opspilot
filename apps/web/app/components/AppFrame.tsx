'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useEffect, useState } from 'react';
import { useAuth } from '../lib/auth';
import type { MessageKey } from '../lib/i18n/en';
import { useLocale } from '../lib/locale';
import { isAdminRole, isManagerRole } from '../lib/roles';
import type { UserRole } from '../lib/api';
import { Icon, type IconName } from './icons';
import { Preferences } from './Preferences';

const PUBLIC_ROUTES = ['/login', '/register'];
const COLLAPSED_KEY = 'opspilot_sidebar_collapsed';

type NavItem = { href: string; label: MessageKey; icon: IconName };
type NavGroup = { label: MessageKey; items: NavItem[] };

function navGroups(role: UserRole | undefined): NavGroup[] {
  const groups: NavGroup[] = [
    {
      label: 'nav.group.work',
      items: isManagerRole(role)
        ? [
            { href: '/', label: 'nav.inbox', icon: 'inbox' },
            { href: '/dashboard', label: 'nav.dashboard', icon: 'dashboard' },
            { href: '/tickets', label: 'nav.tickets', icon: 'tickets' },
          ]
        : [{ href: '/', label: 'nav.myTickets', icon: 'tickets' }],
    },
    {
      label: 'nav.group.directory',
      items: [
        { href: '/properties', label: 'nav.properties', icon: 'properties' },
        { href: '/customers', label: 'nav.customers', icon: 'customers' },
      ],
    },
  ];
  if (isAdminRole(role)) {
    groups.push({
      label: 'nav.group.admin',
      items: [
        { href: '/channels', label: 'nav.channels', icon: 'channels' },
        { href: '/team', label: 'nav.team', icon: 'team' },
      ],
    });
  }
  return groups;
}

// Wraps every signed-in page in the top bar + sidebar; the public pages (login, register) render bare.
export function AppFrame({ children }: { children: React.ReactNode }) {
  const { token, user, logout } = useAuth();
  const { t } = useLocale();
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState(false);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    try {
      setCollapsed(window.localStorage.getItem(COLLAPSED_KEY) === '1');
    } catch {
      /* storage unavailable — start expanded */
    }
  }, []);

  useEffect(() => {
    setOpen(false);
  }, [pathname]);

  if (PUBLIC_ROUTES.includes(pathname) || !token) return <>{children}</>;

  function toggleCollapsed() {
    const next = !collapsed;
    setCollapsed(next);
    try {
      window.localStorage.setItem(COLLAPSED_KEY, next ? '1' : '0');
    } catch {
      /* the choice just won't persist */
    }
  }

  const collapseLabel = collapsed ? t('nav.expand') : t('nav.collapse');

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="topbar-left">
          <button
            type="button"
            className="icon-btn menu-btn"
            onClick={() => setOpen((o) => !o)}
            aria-label={open ? t('nav.closeMenu') : t('nav.openMenu')}
            aria-expanded={open}
          >
            <Icon name={open ? 'close' : 'menu'} />
          </button>
          <span className="nav-brand">
            <span className="nav-brand-mark" />
            <span className="nav-brand-text">OpsPilot</span>
          </span>
        </div>
        <div className="topbar-right">
          <Preferences />
          {user && <span className="nav-user">{user.email}</span>}
          <button onClick={logout} className="btn btn-secondary">
            {t('common.signOut')}
          </button>
        </div>
      </header>

      <div className="app-body">
        {open && <div className="sidebar-backdrop" onClick={() => setOpen(false)} />}
        <aside className={`sidebar${collapsed ? ' sidebar-collapsed' : ''}${open ? ' sidebar-open' : ''}`}>
          <nav aria-label={t('nav.menu')}>
            {navGroups(user?.role).map((group) => (
              <div key={group.label} className="side-group">
                <div className="side-group-label">{t(group.label)}</div>
                {group.items.map((item) => {
                  const active = item.href === '/' ? pathname === '/' : pathname.startsWith(item.href);
                  return (
                    <Link
                      key={item.href}
                      href={item.href}
                      title={t(item.label)}
                      aria-current={active ? 'page' : undefined}
                      className={`side-link${active ? ' side-link-active' : ''}`}
                    >
                      <Icon name={item.icon} />
                      <span className="side-label">{t(item.label)}</span>
                    </Link>
                  );
                })}
              </div>
            ))}
          </nav>
          <button
            type="button"
            className="side-collapse"
            onClick={toggleCollapsed}
            title={collapseLabel}
            aria-label={collapseLabel}
            aria-expanded={!collapsed}
          >
            <Icon name={collapsed ? 'chevron-right' : 'chevron-left'} />
            <span className="side-label">{collapseLabel}</span>
          </button>
        </aside>
        <div className="app-content">{children}</div>
      </div>
    </div>
  );
}
