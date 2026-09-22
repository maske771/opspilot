import type { TicketPriority, TicketStatus } from './api';

export const STATUS_LABELS: Record<TicketStatus, string> = {
  new: 'New',
  assigned: 'Assigned',
  accepted: 'Accepted',
  in_progress: 'In progress',
  completed: 'Completed',
  waiting_approval: 'Waiting approval',
  closed: 'Closed',
};

export const PRIORITY_LABELS: Record<TicketPriority, string> = {
  critical: 'Critical',
  high: 'High',
  medium: 'Medium',
  low: 'Low',
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
