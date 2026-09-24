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
GET   /users
POST  /users
PATCH /users/{id}/role
PATCH /users/{id}/specialties
DELETE /users/{id}
```

All user and organization operations are tenant-scoped. Owner/admin permissions are enforced server-side.

`specialties` is a list of ticket category strings (e.g. `plumbing`, `hvac`, `electrical`) a staff/technician user can be assigned. Used by the ticket auto-assignment engine below.

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
```

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

## Dashboard / analytics

Implemented now:

```text
GET /dashboard/summary
```

`/dashboard/summary` returns tenant-scoped totals for tickets, open tickets, overdue tickets, customers, properties and units, plus complete ticket breakdowns by status and priority. Open tickets are `new`, `assigned`, `accepted`, `in_progress`, and `waiting_approval`. Overdue means a non-closed ticket whose resolution deadline has passed.

Planned next:

```text
GET /dashboard/open-tickets
GET /dashboard/overdue
GET /dashboard/critical
GET /analytics/categories
GET /analytics/sla
GET /analytics/vendors
```

## Internal AI endpoints

These are service-to-service endpoints and must not be exposed as an unrestricted public API:

```text
POST /internal/ai/intake
POST /internal/ai/customer-match
POST /internal/ai/generate-response
POST /internal/ai/analyze-image
POST /internal/ai/daily-report
```

Implemented now: `POST /internal/ai/intake`. The MVP uses a deterministic classifier as a safe baseline for category/priority assignment; it is deliberately structured so a real LLM/agent can replace the classifier later. In production, `INTERNAL_API_KEY` is required.

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
