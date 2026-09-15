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

```text
GET /channels
POST /channels/{type}/connect
POST /channels/{type}/disconnect
GET /channels/{id}
PATCH /channels/{id}
POST /channels/{id}/test
```

## Webhooks

```text
POST /webhooks/line/{account_id}
POST /webhooks/whatsapp/{account_id}
POST /webhooks/telegram/{account_id}
POST /webhooks/email/{account_id}
```

Webhook handlers must validate provider signatures where applicable, persist the inbound event, return success quickly, and enqueue asynchronous processing.

## Conversations/messages

```text
GET /conversations
GET /conversations/{id}
GET /conversations/{id}/messages
```

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
