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
DELETE /users/{id}
```

All user and organization operations are tenant-scoped. Owner/admin permissions are enforced server-side.

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
```

Supported channel types in the MVP are `line`, `whatsapp`, `telegram`, and `email`. Connect/disconnect/configuration operations require `owner` or `admin`. All reads and mutations are organization-scoped.

Connect accepts both a provider `account_id` (the stable external account identifier used by webhooks) and a human-readable `name`.

## Webhooks

Implemented:

```text
POST /webhooks/line/{account_id}
POST /webhooks/whatsapp/{account_id}
POST /webhooks/telegram/{account_id}
POST /webhooks/email/{account_id}
```

Inbound requests are persisted in `webhook_events`. The handler validates `X-Webhook-Signature` using `WEBHOOK_SECRET` when configured. The accepted signature is an HMAC-SHA256 digest of the raw request body; both the raw digest and `sha256=<digest>` forms are accepted. In production, `WEBHOOK_SECRET` is mandatory. Development may accept unsigned requests when no secret is configured.

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
