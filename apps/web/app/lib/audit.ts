import { useCallback } from 'react';
import type { AuditEventRead, PropertyRead, TicketPriority, TicketStatus, UserRead } from './api';
import type { MessageKey } from './i18n/en';
import { useLocale } from './locale';
import { useServices } from './services';
import { PRIORITY_KEYS, STATUS_KEYS } from './ui';

type Change = { from?: unknown; to?: unknown };

const FIELD_KEYS: Record<string, MessageKey> = {
  title: 'audit.field.title',
  description: 'audit.field.description',
  category: 'audit.field.category',
  priority: 'audit.field.priority',
};

const SIMPLE_KEYS: Record<string, MessageKey> = {
  'user.created': 'audit.user.created',
  'user.role_changed': 'audit.user.roleChanged',
  'user.specialties_changed': 'audit.user.specialtiesChanged',
  'user.deleted': 'audit.user.deleted',
  'channel.connected': 'audit.channel.connected',
  'channel.disconnected': 'audit.channel.disconnected',
  'channel.webhook_token_rotated': 'audit.channel.tokenRotated',
  'property.code_regenerated': 'audit.property.codeRegenerated',
  'property.deleted': 'audit.property.deleted',
  'property.services_updated': 'audit.property.servicesUpdated',
  'organization.sla_changed': 'audit.organization.slaChanged',
};

/** Turns an audit event into one human-readable line in the current language. */
export function useAuditText(users: UserRead[], properties: PropertyRead[] = []) {
  const { t, tOr, locale } = useLocale();
  const { label: serviceLabel, services } = useServices();

  const person = useCallback((id: unknown) => (typeof id === 'string' ? users.find((u) => u.id === id)?.email ?? '—' : null), [users]);
  const role = useCallback((value: unknown) => tOr(`role.${value}`, String(value)), [tOr]);
  const status = (value: unknown) => (STATUS_KEYS[value as TicketStatus] ? t(STATUS_KEYS[value as TicketStatus]) : String(value));
  const priority = (value: unknown) => (PRIORITY_KEYS[value as TicketPriority] ? t(PRIORITY_KEYS[value as TicketPriority]) : String(value));

  function fieldValue(field: string, value: unknown): string {
    if (field === 'priority') return priority(value);
    if (field === 'category') return serviceLabel(String(value));
    return String(value ?? '—');
  }

  return useCallback(
    (e: AuditEventRead): string => {
      const d = e.details as Record<string, unknown>;
      const key = `${e.entity_type}.${e.action}`;
      switch (key) {
        case 'ticket.created':
          return t(d.source === 'chat' ? 'audit.ticket.createdChat' : 'audit.ticket.createdManual', {
            service: serviceLabel(String(d.category)),
            priority: priority(d.priority),
          });
        case 'ticket.assigned': {
          const to = person(d.to);
          if (!to) return t('audit.ticket.unassigned');
          return t(d.auto ? 'audit.ticket.autoAssigned' : 'audit.ticket.assigned', { name: to });
        }
        case 'ticket.status_changed':
          return t('audit.ticket.status', { from: status(d.from), to: status(d.to) });
        case 'ticket.updated': {
          const fields = (d.fields ?? {}) as Record<string, Change>;
          const parts = Object.entries(fields).map(([field, c]) => {
            const name = FIELD_KEYS[field] ? t(FIELD_KEYS[field]) : field;
            return 'from' in c ? `${name}: ${fieldValue(field, c.from)} → ${fieldValue(field, c.to)}` : name;
          });
          return t('audit.ticket.updated', { changes: parts.join('; ') });
        }
        case 'ticket.note_added':
          return Number(d.photos) > 0 ? t('audit.ticket.notePhotos', { count: Number(d.photos) }) : t('audit.ticket.note');
        case 'user.role_changed':
          return t('audit.user.roleChanged', { email: String(d.email), from: role(d.from), to: role(d.to) });
        case 'user.created':
        case 'user.deleted':
          return t(SIMPLE_KEYS[key], { email: String(d.email), role: role(d.role) });
        case 'channel.updated':
          return t('audit.channel.updated', { name: String(d.name), fields: ((d.fields as string[]) ?? []).join(', ') });
        case 'customer.property_changed': {
          const to = (d.property_id as Change)?.to;
          const prop = typeof to === 'string' ? properties.find((p) => p.id === to)?.name ?? '—' : t('audit.notLinked');
          return t('audit.customer.propertyChanged', { name: String(d.name ?? '—'), property: prop });
        }
        case 'organization.properties_imported':
          return t('audit.organization.propertiesImported', { properties: Number(d.properties_new), units: Number(d.units_new) });
        case 'organization.renamed':
          return t('audit.organization.renamed', { from: String(d.from), to: String(d.to) });
        case 'service.archived': {
          const names = (d.names ?? {}) as Record<string, string>;
          return t('audit.service.archived', { name: names[locale] ?? names.en ?? String(d.code) });
        }
        default:
          if (SIMPLE_KEYS[key]) return t(SIMPLE_KEYS[key], { email: String(d.email ?? ''), name: String(d.name ?? '') });
          return `${e.entity_type}: ${e.action}`;
      }
    },
    // services is a dependency through serviceLabel
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [t, tOr, locale, person, role, serviceLabel, services, properties],
  );
}
