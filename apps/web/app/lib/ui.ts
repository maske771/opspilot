import type { TicketPriority, TicketStatus } from './api';
import type { MessageKey } from './i18n/en';

export const STATUS_KEYS: Record<TicketStatus, MessageKey> = {
  new: 'status.new',
  assigned: 'status.assigned',
  accepted: 'status.accepted',
  in_progress: 'status.in_progress',
  completed: 'status.completed',
  waiting_approval: 'status.waiting_approval',
  closed: 'status.closed',
};

export const PRIORITY_KEYS: Record<TicketPriority, MessageKey> = {
  critical: 'priority.critical',
  high: 'priority.high',
  medium: 'priority.medium',
  low: 'priority.low',
};

export function statusBadgeStyle(status: TicketStatus): React.CSSProperties {
  return {
    background: `var(--status-${status}-bg)`,
    color: `var(--status-${status}-text)`,
  };
}

export function priorityBadgeStyle(priority: TicketPriority): React.CSSProperties {
  return {
    background: `var(--priority-${priority}-bg)`,
    color: `var(--priority-${priority}-text)`,
  };
}
