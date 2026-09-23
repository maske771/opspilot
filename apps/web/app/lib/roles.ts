import type { UserRole } from './api';

const MANAGER_ROLES: UserRole[] = ['owner', 'admin', 'manager'];
const ADMIN_ROLES: UserRole[] = ['owner', 'admin'];

export function isManagerRole(role: UserRole | undefined): boolean {
  return !!role && MANAGER_ROLES.includes(role);
}

export function isAdminRole(role: UserRole | undefined): boolean {
  return !!role && ADMIN_ROLES.includes(role);
}
