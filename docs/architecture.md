# Architecture

How OpsPilot is built today, and where it still differs from the target design the MVP started from. The API contract is in [`api.md`](api.md); this document is about structure and flow.

## Components

```text
                    ┌──────────── Caddy (TLS) ────────────┐
                    │                                      │
   Browser ──────▶  web (Next.js)          api (FastAPI) ◀── messenger webhooks
                                               │   │
                                               │   ├─ in-process jobs: SLA monitor, daily report scheduler
                                               │   └─ outbound: Telegram / LINE / WhatsApp / SMTP
                                               ▼
                                        PostgreSQL 17  ◀── postgres-exporter
                                               │
                            media volume (/media, customer photos)

   Prometheus ◀── api /metrics, cAdvisor, postgres-exporter ──▶ Alertmanager → Telegram
   Grafana ── dashboards over Prometheus
```

Everything runs as Docker Compose services on one VPS (`docker-compose.prod.yml`).

## Inbound message pipeline

All of this happens synchronously inside the webhook request (`webhook_routes.py` → `webhook_service.py`):

1. **Authenticate** the webhook against the target channel: per-channel token (query or header), Telegram's secret-token header, or an HMAC signature (`webhook_auth.py`).
2. **Persist** the raw event in `webhook_events`; a repeated provider event id is ignored (idempotency).
3. **Normalize** the provider payload into a common event (text, sender, conversation, optional photo).
4. **Match or create the customer** (`customer_match.py`) via `customer_identities` (one customer can have identities in several channels). Display names are never used to merge customers.
5. **Staff commands** (`/link CODE`, `/start CODE`) are handled separately (`staff_link.py`) and never create customer conversations.
6. **Registration**: if the organization has properties, the customer isn't linked to one, and there's no open ticket in the conversation, the bot asks for the **property code** and remembers the request (`conversations.pending_step`, `pending_message_id`). A valid code links the customer and turns the remembered request into a ticket.
7. **Classification** against the organization's **service catalog** (`services`): keyword match, the most severe matching service wins; nothing matched → the system "Other" service for manual sorting. For a linked customer at a configured property, only that property's services are considered. Greetings and thanks don't open tickets; status questions are answered without opening one; a different problem while a ticket is open gets its own ticket (rules in [`api.md`](api.md#webhooks)).
8. **Ticket**: priority from the service, SLA deadlines resolved per priority as *property+service → organization → built-in* (`services.sla_overrides_for`, `sla.calculate_sla`), auto-assignment to the least-loaded staff/technician linked to the service (`assignment.py`).
9. **Reply** to the customer in their language (EN/RU/TH), asking for a photo when none was sent (`ai_response.py`), sent through the channel adapter (`outbound.py`). Customer photos are downloaded to the media volume.

## Ticket lifecycle

`new → assigned → accepted → in_progress → completed → closed`, with `waiting_approval` before closing for high/critical tickets (manager approval). `first_responded_at` is stamped when a ticket first leaves new/assigned, `closed_at` on close — both feed SLA analytics.

## Background jobs

Two asyncio loops start with the API (`main.py` lifespan). Each takes its own Postgres advisory lock per tick, so running several API instances wouldn't double-send.

- **SLA monitor** (`sla_monitor.py`, every 30 s): "due soon", "overdue" and escalation notices to staff and managers over Telegram, each sent at most once per ticket, recipient and kind (`ticket_notifications`).
- **Daily report scheduler** (`daily_report_scheduler.py`, every 60 s): sends each organization's daily summary to managers at its configured time and timezone, honoring skipped weekends/dates and a custom message template.

Staff receive notifications only after linking their Telegram from their profile.

## Data model (main tables)

| Area | Tables |
|---|---|
| Tenancy and people | `organizations`, `users` (roles: owner, admin, manager, staff, technician; `specialties` = service codes) |
| Catalog and places | `services`, `properties` (with resident `code`), `units`, `property_services` (+ per-priority SLA) |
| Customers and conversations | `customers` (+ `property_id`, `unit_id`), `customer_identities`, `channels`, `conversations`, `messages`, `message_attachments`, `webhook_events` |
| Work | `tickets`, `ticket_notes` + `ticket_note_attachments` (work log), `ticket_notifications` |
| Audit | `audit_events` (ticket history and sensitive admin actions) |

Every tenant-owned row carries `organization_id`; every query is scoped to the caller's organization in the API layer. Schema changes are numbered SQL files in `database/migrations`.

## Security, as implemented

- JWT auth; role checks server-side on every endpoint.
- Webhooks are never accepted unauthenticated; per-channel tokens can be rotated.
- Bot tokens and other provider tokens are masked in logs (`log_redaction.py`) and never returned by the API.
- Customer photos are served only through an authenticated endpoint.

## Observability

The API exposes Prometheus metrics at `/metrics`. Prometheus scrapes it plus cAdvisor and postgres-exporter; Alertmanager forwards alerts to Telegram; Grafana dashboards are provisioned from `monitoring/grafana`.

## Where the build differs from the target design

The original design called for the items on the left. These are deliberate MVP shortcuts, not oversights.

| Target | Today |
|---|---|
| Webhooks acknowledge fast and enqueue work for async workers | Everything runs inside the webhook request. Fine at current volume; slows provider acknowledgements as traffic grows. |
| Separate worker processes and a queue | In-process asyncio loops with advisory locks. |
| AI agents (intake, response, image proof, analytics) | Rule-based: catalog keywords for intake, templates for replies. See [`ai-agents.md`](ai-agents.md). |
| Channel credentials in a dedicated secret store | Stored in the `channels.credentials` JSONB column, masked everywhere they could leak. |
| Media in private object storage with signed URLs | Local disk volume behind an authenticated endpoint; needs backups, doesn't scale past one API instance. |
| Audit events for sensitive changes | Done: `audit_events` is written in the same transaction as the change (ticket lifecycle; roles, channels, customer↔property links, property codes, SLA, archived services). Never stores credentials or tokens. |
| Configurable data retention (Thai PDPA) | Not implemented. |
| Dead-letter queue and retries for provider/AI failures | Only staff notifications retry (3 attempts); failed customer replies aren't retried. |
| Channel health state | Channels have a connected/disconnected status, no health checks. |

## Deployment

`scripts/deploy-prod.sh` renders `infra/caddy/Caddyfile` from `Caddyfile.template` using values from the server's `.env` (domain, Prometheus basic-auth), then runs `docker compose -f docker-compose.prod.yml up -d --build`, which rebuilds and restarts whatever changed. Migrations are applied by hand to the running database (see the README). Caddy terminates TLS for the product, the API and the monitoring UIs.
