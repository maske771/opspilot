# API Contract — MVP v0.1

## Authentication

```text
POST /auth/register
POST /auth/login
POST /auth/refresh
POST /auth/logout
GET  /auth/me
```

## Organization / users

```text
GET   /organization
PATCH /organization
GET   /organization/sla
PATCH /organization/sla
GET   /users
POST  /users
PATCH /users/{id}/role
PATCH /users/{id}/specialties
DELETE /users/{id}
```

All user and organization operations are tenant-scoped. Owner/admin permissions are enforced server-side.

`specialties` is a list of ticket category strings (e.g. `plumbing`, `hvac`, `electrical`) a staff/technician user can be assigned. Used by the ticket auto-assignment engine below.

`PATCH /organization` accepts a partial body (`name`, `onboarding_completed`) — omitted fields are left unchanged. `onboarding_completed` defaults to `false` on a new organization and gates the web app's `/onboarding` setup wizard (owner/admin only): a walkthrough of company name, connecting a channel, adding a property, inviting a teammate, reviewing the recommended SLA (`GET /sla/defaults`, read-only), sending a test request, and marking the organization live. Visiting `/onboarding` once `onboarding_completed` is `true` redirects to the dashboard. CSV/XLSX property import from `product-spec.md`'s onboarding flow is not implemented — deferred, properties are added one at a time.

`GET/PUT /properties/{id}/services` (owner/admin only) — which services a property gets and its SLA per service and priority (`sla: {"<priority>": {response_minutes, resolution_minutes}}`, 1–43200). PUT replaces the whole list; an empty list resets the property to "not configured", which means every active service with the organization SLA. GET returns, per active service, `enabled`, the property's own `overrides`, and the effective `sla` per priority with its `source` (`property` / `organization` / `default`). Ticket deadlines resolve per priority in that order — property+service, then organization, then built-in — on creation and whenever the ticket's priority or service changes.

`/organization/sla` (GET and PATCH, owner/admin only) — the web app's `/settings` screen. Returns one row per `TicketPriority` (`priority`, `response_minutes`, `resolution_minutes`, `is_custom`): the organization's *effective* SLA targets, i.e. its own override (`Organization.sla_overrides`, a JSONB map keyed by priority value) where set, otherwise the built-in default from `sla.SLA_MINUTES`. PATCH takes a partial body keyed by priority (`critical`/`high`/`medium`/`low`), each either `{response_minutes, resolution_minutes}` (both required together, 1–43200) to set an override or `null` to clear that priority back to default; priorities omitted from the body are left untouched. New tickets — from `POST /tickets`, a priority change via `PATCH /tickets/{id}`, and webhook-created tickets — look up the organization's override at creation/recalculation time via `sla.calculate_sla(priority, created_at, overrides)`.

## Properties / units

```text
GET   /properties
POST  /properties
GET   /properties/{id}
PATCH /properties/{id}
DELETE /properties/{id}

GET   /properties/{id}/units
POST  /properties/{id}/units
GET   /units/{id}
PATCH /units/{id}
DELETE /units/{id}

POST  /properties/import/preview    multipart: file (.csv UTF-8 or .xlsx, ≤ 1 MB, ≤ 5000 rows)
POST  /properties/import            same file; owner/admin/manager
```

Bulk import: one row per unit with columns `property`, `address` (optional), `unit` (optional); headers are also accepted in Russian (`объект`, `адрес`, `квартира`) and Thai (`อาคาร`, `ที่อยู่`, `ห้อง`), CSV delimiter `,` `;` or tab. Rows group by property name; a name that already exists (case-insensitive) adds units to that property and leaves its address alone. Units already on the property or repeated in the file are skipped. Both endpoints return the same plan (`properties`, `properties_new`, `properties_existing`, `units_new`, `units_skipped`, `errors: [{row, code}]` with spreadsheet row numbers). The import refuses a file with row errors (`422 rows_have_errors`) and otherwise writes everything in one transaction plus a `properties_imported` audit event. File-level errors come back as codes in `detail`: `empty_file`, `no_property_column`, `not_utf8`, `unsupported_file`, `too_many_rows`, `file_too_large`.

## Customers

```text
GET   /customers
POST  /customers
GET   /customers/{id}
PATCH /customers/{id}
GET   /customers/{id}/identities
```

## Channels

Implemented:

```text
GET  /channels
POST /channels/{type}/connect
POST /channels/{type}/disconnect
GET  /channels/{id}
PATCH /channels/{id}
POST /channels/{id}/test
POST /channels/{id}/rotate-webhook-token
POST /channels/{id}/register-webhook
```

Supported channel types in the MVP are `line`, `whatsapp`, `telegram`, and `email`. Connect/disconnect/configuration operations require `owner` or `admin`. All reads and mutations are organization-scoped.

`POST /channels/telegram/connect`'s response carries `bot_username` (best-effort, via Telegram's `getMe`) so the caller can build a `t.me/<username>` deep link right after connecting; it's `null` for non-telegram channels and not otherwise persisted or returned by `GET /channels`.

```text
GET /sla/defaults
```

`/sla/defaults` returns the built-in response/resolution SLA targets per priority (`sla.SLA_MINUTES`) — read-only, any authenticated user. There is no per-organization SLA override yet; that's tracked as a future Settings-screen item.

Every channel has a random `webhook_token`. It authenticates inbound webhooks, so it is returned only to `owner`/`admin` (other roles see `null`). `rotate-webhook-token` replaces it (the old webhook URL stops working at once). `register-webhook` (Telegram only) points the bot's webhook at the channel; this also happens automatically on connect, on credential/status changes, on token rotation and at API start. It needs `PUBLIC_API_URL` (e.g. `https://api.example.com`) to be set on the server.

Connect accepts both a provider `account_id` (the stable external account identifier used by webhooks) and a human-readable `name`.

## Webhooks

Implemented:

```text
POST /webhooks/line/{account_id}
POST /webhooks/whatsapp/{account_id}
POST /webhooks/telegram/{account_id}
POST /webhooks/email/{account_id}
GET  /webhooks/whatsapp/{account_id}   (Meta verification handshake)
```

Inbound requests are persisted in `webhook_events`. Every request must authenticate against the connected channel it targets, in any of these ways:

- the channel's `webhook_token` as the `token` query parameter (works for every provider: register the URL `.../webhooks/{provider}/{account_id}?token=...`);
- the same token in the `X-Webhook-Token` header, or in Telegram's `X-Telegram-Bot-Api-Secret-Token` header (set through `setWebhook`'s `secret_token`, which the API does automatically);
- an `X-Webhook-Signature` header: HMAC-SHA256 of the raw body with `WEBHOOK_SECRET` (raw digest or `sha256=<digest>`). This never passes when `WEBHOOK_SECRET` is unset.

Anything else gets `401 Invalid webhook credentials`, the same answer whether or not the channel exists, so channel ids cannot be enumerated. There is no unauthenticated mode, in development or production. For WhatsApp, the `hub.verify_token` of the GET handshake is the channel's `webhook_token`.

`X-Event-Id` is used for idempotency; when absent, the payload `event_id`/`id` is used, otherwise a UUID is generated. Duplicate events for the same organization/provider/account/event ID are ignored.

Supported inbound events are normalized into the domain model: `CustomerIdentity` → `Customer` → `Conversation` → `Message`. A new non-closed ticket is created for a conversation when one does not already exist. Unsupported/unrecognized provider payloads are still accepted and stored, but return `normalized: false` for later processing.

Incoming requests are routed by the organization's **service catalog** (`GET/POST /services`, `PATCH/DELETE /services/{id}`; listing for any signed-in user, changes owner/admin only). Each service has names (en/ru/th), keywords (case-insensitive substring match, any language) and a default priority; when several services match, the more severe one wins. Nothing matched → the system `other` service (not removable, no keywords) for manual sorting. A new organization's catalog is seeded from the old built-in categories on first use. Tickets (`category`) and executors (`specialties`, used by auto-assignment) reference a service by its immutable `code`; both are validated against the active catalog. `DELETE` archives rather than deletes — old tickets keep their label (`GET /services?include_archived=true`), new requests stop matching it, and executors are unlinked.

**Registration by property code.** Every property has a short `code` (6 chars, no 0/O/1/I; shown in `PropertyRead`, new one via `POST /properties/{id}/regenerate-code`, owner/admin/manager) that managers hand out to residents. If an organization has properties and a customer who isn't linked to one writes without an open ticket, the bot asks for the code instead of opening a ticket (conversation `pending_step = "property_code"`), remembering their first actionable message (`pending_message_id`). A valid code (case and separators ignored) links the customer (`Customer.property_id`) and turns that remembered message into a ticket on the property; a wrong code gets "not found", a non-code reply gets the question again. Afterwards the link only changes through `PATCH /customers/{id}` (`property_id`, `unit_id` — owner/admin/manager only; the unit must belong to the property and is cleared when the property changes). If a manager links the customer while the bot is still waiting, the next message unblocks the dialog and the remembered request becomes a ticket. Organizations without properties, and customers with an already open ticket, are never asked. Linked customers' tickets get `property_id`/`unit_id`, are classified only among the property's services (when configured), and use its SLA.

When a new ticket is created, the customer gets an automatic acknowledgement (`ai_response.RuleBasedResponseGenerator`) localized to their detected language. Unless the triggering message already had a photo attached, the acknowledgement appends a one-line request to send one — for every category except `emergency` (asking would delay a safety response). This deliberately includes `other`: an unclassified message is exactly when a photo helps most. Follow-up messages on an open ticket get the same request appended to their generic acknowledgement until a photo is on file for that ticket (any attachment in the conversation since the ticket was created); status questions ("any update?") are answered without it.

**Dialog rules** (`webhook_service._dialog_step`, covered scenario by scenario in `tests/test_dialog_scenarios.py`): small talk (a message made only of greetings, thanks, acknowledgements — "hi there, the gate is broken" is a request) gets a short reply and never opens a ticket; a status question (a status word in a question or a ≤4-word message) is answered with the latest ticket's status, or "no requests yet", without opening one; only tickets not yet completed take follow-ups; a message naming a *different* service than the open ticket opens a second ticket; the explanation after a vague first message ("I have a problem" → `other`) re-sorts that same ticket while it's still new/assigned; the language is taken from the latest message that has one (a code, photo or "ok" keep the conversation's language).

## Conversations/messages

Implemented read API:

```text
GET /conversations
GET /conversations/{id}
GET /conversations/{id}/messages
```

Conversation and message reads are organization-scoped. Messages are returned chronologically. Creation of conversations/messages is reserved for webhook/provider ingestion and is not exposed as a general-purpose public write endpoint.

## Tickets

```text
GET   /tickets
POST  /tickets
GET   /tickets/{id}
PATCH /tickets/{id}

POST /tickets/{id}/assign
POST /tickets/{id}/accept
POST /tickets/{id}/start
POST /tickets/{id}/complete
POST /tickets/{id}/close
```

Tickets may optionally reference the originating conversation via `conversation_id`.

On creation (both `POST /tickets` and webhook-generated tickets), the auto-assignment engine looks for a `staff`/`technician` user in the organization whose `specialties` include the ticket's `category`, and picks the one with the fewest currently open (non-closed) tickets. If a match is found, the ticket is assigned and moves straight to `assigned`; otherwise it is left unassigned in `new` for manual triage.

### Work log

```text
GET  /tickets/{id}/notes
POST /tickets/{id}/notes            multipart/form-data: body (text, optional), photos (0–5 files)
GET  /ticket-attachments/{id}       image bytes
```

Any user of the organization can read the log and add entries; executors use it to record what was done and attach before/after photos. An entry needs text or at least one photo (`422` otherwise). Photos must be JPEG, PNG or WebP — detected from the file's bytes, not its name (`415`) — at most 10 MB each (`413`) and 5 per entry (`422`). Body text is capped at 5000 characters. Closed tickets are read-only (`409`). Photos are stored like chat photos (local media volume) and served only to users of the same organization.

### History and audit log

```text
GET /tickets/{id}/history                 any user of the organization; oldest first
GET /audit-events?entity_type=&entity_id=&limit=&offset=   owner/admin; newest first (limit ≤ 500)
```

Each event: `actor_id`/`actor_email` (null = the system, e.g. chat-created tickets or auto-assignment), `entity_type`, `entity_id`, `action`, `details`, `created_at`. Events are written in the same transaction as the change.

| entity_type | actions |
|---|---|
| `ticket` | `created` (`source`: manual/chat), `assigned` (`from`/`to`, `auto`), `status_changed` (`from`/`to`), `updated` (`fields`: per field `from`/`to`; description only notes the change), `note_added` |
| `user` | `created`, `role_changed`, `specialties_changed`, `deleted` |
| `channel` | `connected`, `disconnected`, `webhook_token_rotated`, `updated` (field names only — never credentials or tokens) |
| `customer` | `property_changed` |
| `property` | `code_regenerated` (the code itself is not stored), `services_updated`, `deleted` |
| `organization` | `renamed`, `sla_changed` |
| `service` | `archived` |

### Manager approval for high/critical closure

`POST /tickets/{id}/complete` on a `high`/`critical` ticket moves it to `waiting_approval` instead of `completed` (per `docs/product-spec.md`'s "high/critical closure requires human approval"), and notifies every `owner`/`admin`/`manager` in the organization once, immediately (`notify_managers_approval_needed`, not the polling SLA monitor). `low`/`medium` tickets complete as before.

`POST /tickets/{id}/close` on a `high`/`critical` ticket (in any status — a manager may also close one directly, e.g. a duplicate/spam report, without going through `complete` first) requires the caller's role to be `owner`, `admin` or `manager`; anyone else gets `403`. `low`/`medium` tickets can still be closed by anyone, unchanged.

## Staff notifications and SLA monitor

Staff hear about their work through the organization's Telegram bot.

```text
GET    /me/telegram              { linked, channel_available }
POST   /me/telegram-link-code    { code, expires_at, deep_link }   (409 when no Telegram bot is connected)
DELETE /me/telegram-link
```

Linking: a signed-in user requests a code (8 characters, valid 10 minutes, single use, scoped to their organization) and sends `/link CODE` — or opens the `t.me/<bot>?start=CODE` deep link, which sends `/start CODE` — to the bot in a private chat. The webhook binds that chat to the user, remembers their Telegram language (`en`/`ru`/`th`, English otherwise) for all later messages, and confirms. Link commands never create customer conversations or tickets. `GET /users` exposes `telegram_linked`.

A background monitor (`sla_monitor.py`, started with the API, every `SLA_WORKER_INTERVAL_SECONDS`, default 30; disable with `SLA_WORKER_ENABLED=false`; guarded by a Postgres advisory lock) looks at open tickets and sends, each **at most once per ticket, recipient and kind** (`ticket_notifications`):

| Kind | Recipient | When |
|---|---|---|
| `assigned` | assignee | ticket is assigned (auto, manual or reassigned), created within the last 48 h |
| `response_soon` / `resolution_soon` | assignee | 20 % (min 2 min) / 10 % (min 5 min) of the SLA window is left |
| `response_overdue` / `resolution_overdue` | assignee | the deadline has passed |
| `escalation_response` / `escalation_resolution` | owner, admins and managers of the organization (not the assignee twice) | the deadline has passed; also when nobody is assigned |

The response deadline applies while the ticket is `new` or `assigned`; the resolution deadline until it is `completed`, `waiting_approval` or `closed`. Deadlines missed more than 24 h ago are treated as history and not announced. A failed send is retried up to 3 times; recipients without a linked Telegram are recorded as `skipped` and not retried. Messages are localized and carry a link to the ticket built from `PUBLIC_WEB_URL`.

Environment: `PUBLIC_WEB_URL` (links in messages), `SLA_WORKER_INTERVAL_SECONDS`, `SLA_WORKER_ENABLED`, and `TELEGRAM_API_BASE` (defaults to `https://api.telegram.org`; lets tests and local runs use a fake server).

## Dashboard / analytics

Implemented now:

```text
GET /dashboard/summary
```

`/dashboard/summary` returns tenant-scoped totals for tickets, open tickets, overdue tickets, customers, properties and units, plus complete ticket breakdowns by status and priority. Open tickets are `new`, `assigned`, `accepted`, `in_progress`, and `waiting_approval`. Overdue means a non-closed ticket whose resolution deadline has passed.

```text
GET   /reports/daily?date=YYYY-MM-DD
GET   /reports/daily/settings
PATCH /reports/daily/settings
```

`/reports/daily` — the "daily operations summary" from `docs/product-spec.md` (MVP workflow step 13), `owner`/`admin`/`manager` only (`403` otherwise). `date` is optional and defaults to yesterday; both default and explicit dates are read as a calendar day in the organization's timezone (`Organization.daily_report_timezone`, default `Asia/Bangkok`). Returns: tickets created that day (total + by priority + by category), tickets closed that day (via `Ticket.closed_at`, stamped whenever a ticket transitions to `closed`), and a *current* snapshot (not scoped to the report day) of open/overdue/waiting-approval counts plus the list of currently open `high`/`critical` tickets with assignee and an `overdue` flag.

`/reports/daily/settings` (GET and PATCH) — controls automatic delivery of the report over Telegram, `owner`/`admin` only (`403` otherwise). Fields: `daily_report_enabled` (bool, default `false`), `daily_report_time` (`"HH:MM"` 24h, default `"08:00"`), `daily_report_timezone` (one of a curated 16-zone allowlist, `ALLOWED_TIMEZONES` in `report_routes.py`; default `"Asia/Bangkok"`), `daily_report_skip_weekends` (bool, default `false` — also skips Saturday/Sunday in the org's timezone), `daily_report_excluded_dates` (list of `YYYY-MM-DD`, default `[]` — specific dates to skip, e.g. public holidays; send the full desired list on PATCH, not a delta). PATCH accepts a partial body — omitted fields are left unchanged; `daily_report_excluded_dates: []` clears it. Exposed inline on the web app's Daily report page rather than a separate settings screen.

`daily_report_template` (GET: `dict[lang, text]`, always one entry per `en`/`ru`/`th` — the organization's own override where set, otherwise the built-in default; `daily_report_template_custom`: `dict[lang, bool]` says which ones are actually overridden). PATCH takes a partial `dict[lang, text | null]` — a string sets that language's override, `null` clears it back to default, languages omitted are untouched. A template string must successfully `.format()` against the same placeholders the scheduler renders with (`date`, `created`, `closed`, `open`, `overdue`, `waiting`, `critical`, `url`) — an unknown placeholder or malformed `{...}` is rejected with `422` at save time. `daily_report_scheduler.py` renders through `notifications.render_daily_report()`, which prefers the organization's template for the recipient's language and falls back to the built-in one on any render-time error, as a second safety net beyond the save-time validation.

A background scheduler (`daily_report_scheduler.py`, started with the API, every `DAILY_REPORT_WORKER_INTERVAL_SECONDS`, default 60; disable with `DAILY_REPORT_WORKER_ENABLED=false`; its own Postgres advisory lock, separate from the SLA monitor's) ticks over every organization with delivery enabled and, once the current time in the org's own timezone has passed `daily_report_time`, today isn't a skipped weekend/excluded date, and today's report hasn't already gone out (`Organization.daily_report_last_sent_date`), sends the previous day's report to every `owner`/`admin`/`manager` with Telegram linked, localized per recipient (using the org's custom template where set), with a link built from `PUBLIC_WEB_URL`. An unknown/invalid timezone is skipped (logged), not crashed. A day skipped for weekend/excluded-date reasons never touches `daily_report_last_sent_date`, so delivery resumes normally on the next eligible day. Delivery is per-organization and idempotent per calendar day in that org's timezone.

```text
GET /analytics/overview?from=YYYY-MM-DD&to=YYYY-MM-DD
```

`/analytics/overview` — the `/analytics` web screen, `owner`/`admin`/`manager` only (`403` otherwise). Both `from`/`to` are optional; default is the last 30 days ending today in the organization's timezone (same `org_timezone()` helper the daily report uses). A reversed range is swapped, not rejected; a range longer than 365 days is clamped. Returns:

- `volume`: one row per calendar day in range (`date`, `created`, `closed`) — the gaps are filled with zeros so a line chart stays continuous.
- `by_category` / `by_property` / `by_staff`: counts (and, for category/staff, `avg_resolution_minutes` over tickets *closed* in range) grouped from `Ticket.category` / `property_id` / `assignee_id`. `by_category`'s `created` count and `by_staff`'s `closed` count are scoped independently (a category can have tickets created in range with none closed yet, and vice versa).
- `sla.response` / `sla.resolution`: `{met, missed, pending, met_pct}` over the cohort of tickets *created* in range. `met_pct` excludes `pending` from its denominator. Resolution compares `Ticket.closed_at` against `resolution_deadline`; response compares the new `Ticket.first_responded_at` (see below) against `response_deadline`. A ticket with a passed deadline and no completion timestamp counts as `missed`, not silently dropped.

`Ticket.first_responded_at` (migration 013) is stamped once, the first time a ticket's status leaves `new`/`assigned` (mirroring `sla_monitor.py`'s `RESPONSE_OPEN` — the same set the response deadline applies to). Auto-assignment on creation stays inside that set and is not counted as a response; accepting, starting, completing or closing a ticket is.

## Internal AI endpoints

These are service-to-service endpoints and must not be exposed as an unrestricted public API:

```text
POST /internal/ai/intake
POST /internal/ai/customer-match
POST /internal/ai/generate-response
POST /internal/ai/analyze-image
POST /internal/ai/daily-report
```

Implemented now: `intake`, `customer-match`, `generate-response` — all rule-based, no LLM (see `ai-agents.md`). `intake` classifies with the built-in default rules because it has no organization context; the webhook path classifies against each organization's own service catalog. `analyze-image` and `daily-report` are not implemented. In production, `INTERNAL_API_KEY` is required.

## Standard error shape

```json
{
  "error": {
    "code": "TICKET_NOT_FOUND",
    "message": "Ticket was not found",
    "request_id": "uuid"
  }
}
```

All endpoints must enforce organization scope and server-side RBAC.
