export const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

type FetchOptions = {
  method?: string;
  body?: unknown;
  token?: string | null;
};

export async function apiFetch<T>(path: string, options: FetchOptions = {}): Promise<T> {
  const { method = 'GET', body, token } = options;
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  if (token) headers.Authorization = `Bearer ${token}`;

  const response = await fetch(`${API_BASE}${path}`, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
    cache: 'no-store',
  });

  if (!response.ok) {
    let detail = response.statusText;
    try {
      const data = await response.json();
      detail = data.detail ?? detail;
    } catch {
      /* response had no JSON body */
    }
    throw new ApiError(response.status, detail);
  }

  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export type UserRole = 'owner' | 'admin' | 'manager' | 'staff' | 'technician';

export type UserRead = {
  id: string;
  organization_id: string;
  email: string;
  role: UserRole;
  specialties: string[];
};

export type TicketStatus =
  | 'new'
  | 'assigned'
  | 'accepted'
  | 'in_progress'
  | 'completed'
  | 'waiting_approval'
  | 'closed';

export type TicketPriority = 'critical' | 'high' | 'medium' | 'low';

export type TicketRead = {
  id: string;
  organization_id: string;
  customer_id: string | null;
  property_id: string | null;
  unit_id: string | null;
  conversation_id: string | null;
  title: string;
  description: string;
  category: string;
  priority: TicketPriority;
  status: TicketStatus;
  assignee_id: string | null;
  response_deadline: string | null;
  resolution_deadline: string | null;
  created_at: string;
  updated_at: string;
};

export type PropertyRead = {
  id: string;
  organization_id: string;
  name: string;
  address: string | null;
};

export type UnitRead = {
  id: string;
  organization_id: string;
  property_id: string;
  unit_number: string;
};

export type CustomerRead = {
  id: string;
  organization_id: string;
  name: string | null;
  phone: string | null;
  email: string | null;
};

export type ChannelType = 'telegram' | 'line' | 'whatsapp' | 'email';

export type ChannelRead = {
  id: string;
  organization_id: string;
  type: ChannelType;
  account_id: string;
  name: string;
  status: 'connected' | 'disconnected';
  has_credentials: boolean;
  webhook_token: string | null;
  created_at: string;
};

export type AttachmentRead = {
  id: string;
  content_type: string;
};

export type MessageRead = {
  id: string;
  conversation_id: string;
  direction: 'inbound' | 'outbound';
  content: string;
  external_message_id: string | null;
  created_at: string;
  attachments: AttachmentRead[];
};

export type InboxItem = {
  conversation_id: string;
  customer: { id: string; name: string | null } | null;
  channel: { id: string; type: string; name: string };
  last_message: { content: string; direction: 'inbound' | 'outbound'; created_at: string } | null;
  ticket: { id: string; status: TicketStatus; priority: TicketPriority; assignee_id: string | null } | null;
  updated_at: string;
};

export type DashboardSummary = {
  tickets_total: number;
  tickets_open: number;
  tickets_overdue: number;
  customers_total: number;
  properties_total: number;
  units_total: number;
  tickets_by_status: { status: TicketStatus; count: number }[];
  tickets_by_priority: { priority: TicketPriority; count: number }[];
};
