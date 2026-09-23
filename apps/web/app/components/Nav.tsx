'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useAuth } from '../lib/auth';
import { isAdminRole, isManagerRole } from '../lib/roles';

const MANAGER_LINKS = [
  { href: '/', label: 'Inbox' },
  { href: '/dashboard', label: 'Dashboard' },
  { href: '/tickets', label: 'Tickets' },
  { href: '/properties', label: 'Properties' },
  { href: '/customers', label: 'Customers' },
];

const ADMIN_LINKS = [
  { href: '/channels', label: 'Channels' },
  { href: '/team', label: 'Team' },
];

const FIELD_LINKS = [
  { href: '/', label: 'My Tickets' },
  { href: '/properties', label: 'Properties' },
  { href: '/customers', label: 'Customers' },
];

export function Nav() {
  const { user, logout } = useAuth();
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
                {link.label}
              </Link>
            );
          })}
        </nav>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
        {user && <span style={{ fontSize: 13, color: 'var(--color-text-muted)' }}>{user.email}</span>}
        <button onClick={logout} className="btn btn-secondary">
          Выйти
        </button>
      </div>
    </header>
  );
}
