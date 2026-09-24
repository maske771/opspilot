'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useAuth } from '../lib/auth';
import type { MessageKey } from '../lib/i18n/en';
import { useLocale } from '../lib/locale';
import { isAdminRole, isManagerRole } from '../lib/roles';
import { Preferences } from './Preferences';

type NavLink = { href: string; label: MessageKey };

const MANAGER_LINKS: NavLink[] = [
  { href: '/', label: 'nav.inbox' },
  { href: '/dashboard', label: 'nav.dashboard' },
  { href: '/tickets', label: 'nav.tickets' },
  { href: '/properties', label: 'nav.properties' },
  { href: '/customers', label: 'nav.customers' },
];

const FIELD_LINKS: NavLink[] = [
  { href: '/', label: 'nav.myTickets' },
  { href: '/properties', label: 'nav.properties' },
  { href: '/customers', label: 'nav.customers' },
];

const ADMIN_LINKS: NavLink[] = [
  { href: '/channels', label: 'nav.channels' },
  { href: '/team', label: 'nav.team' },
];

export function Nav() {
  const { user, logout } = useAuth();
  const { t } = useLocale();
  const pathname = usePathname();
  const baseLinks = isManagerRole(user?.role) ? MANAGER_LINKS : FIELD_LINKS;
  const links = isAdminRole(user?.role) ? [...baseLinks, ...ADMIN_LINKS] : baseLinks;

  return (
    <header className="nav">
      <div style={{ display: 'flex', alignItems: 'center', gap: 28 }}>
        <span className="nav-brand">
          <span className="nav-brand-mark" />
          OpsPilot
        </span>
        <nav className="nav-links">
          {links.map((link) => {
            const active = link.href === '/' ? pathname === '/' : pathname.startsWith(link.href);
            return (
              <Link key={link.href} href={link.href} className={`nav-link${active ? ' nav-link-active' : ''}`}>
                {t(link.label)}
              </Link>
            );
          })}
        </nav>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
        <Preferences />
        {user && <span className="nav-user">{user.email}</span>}
        <button onClick={logout} className="btn btn-secondary">
          {t('common.signOut')}
        </button>
      </div>
    </header>
  );
}
