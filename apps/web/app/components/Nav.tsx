'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useAuth } from '../lib/auth';

const links = [
  { href: '/', label: 'Dashboard' },
  { href: '/tickets', label: 'Tickets' },
];

export function Nav() {
  const { user, logout } = useAuth();
  const pathname = usePathname();

  return (
    <header
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '14px 32px',
        borderBottom: '1px solid #e5e7eb',
        background: '#fff',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 28 }}>
        <span style={{ fontWeight: 800, fontSize: 16 }}>OpsPilot</span>
        <nav style={{ display: 'flex', gap: 18 }}>
          {links.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              style={{
                fontSize: 14,
                color: pathname === link.href ? '#111827' : '#6b7280',
                fontWeight: pathname === link.href ? 700 : 400,
                textDecoration: 'none',
              }}
            >
              {link.label}
            </Link>
          ))}
        </nav>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
        {user && <span style={{ fontSize: 13, color: '#6b7280' }}>{user.email}</span>}
        <button
          onClick={logout}
          style={{
            padding: '7px 12px',
            borderRadius: 8,
            border: '1px solid #d1d5db',
            background: '#fff',
            fontSize: 13,
            cursor: 'pointer',
          }}
        >
          Выйти
        </button>
      </div>
    </header>
  );
}
