# API Contract — MVP v0.1

## Authentication

```text
POST /auth/register
POST /auth/login
POST /auth/refresh
POST /auth/logout
```

## Organization

```text
GET   /organization
PATCH /organization
```

## Properties / units

```text
GET   /properties
POST  /properties
GET   /properties/{id}
PATCH /properties/{id}
DELETE /properties/{id}

GET   /properties/{id}/units
POST  /properties/{id}/units
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
GET   /channels
POST  /channels/{type}/connect
POST  /channels/{type}/disconnect
GET   /channels/{id}
PATCH /channels/{id}
POST  /channels/{id}/test
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

```text
GET /dashboard/summary
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
