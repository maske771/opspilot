import type { UserRole } from './api';

const MANAGER_ROLES: UserRole[] = ['owner', 'admin', 'manager'];

export function isManagerRole(role: UserRole | undefined): boolean {
  return !!role && MANAGER_ROLES.includes(role);
}
