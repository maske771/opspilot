# Architecture — MVP v0.1

## High-level flow

```text
LINE / WhatsApp / Telegram / Email
              |
       Channel Adapters
              |
       Normalize Event
              |
             Queue
              |
       Customer Identity
              |
          AI Intake
              |
      Deterministic Rules
        /      |       \
   Priority  Assignment  SLA
        \      |       /
             Ticket
              |
       Notifications
              |
          Staff/Vendor
              |
       Completion + Media
              |
       AI advisory check
              |
        Close / Approve
              |
          Analytics
```

## Application layers

### Web

Next.js application containing onboarding, dashboard, unified inbox, tickets, properties, team, channels and analytics.

### API

FastAPI service responsible for authentication, authorization, tenant scoping, CRUD APIs, webhook intake, ticket workflows and integration with background jobs.

### Database

PostgreSQL. Every tenant-owned record is scoped by `organization_id` and access is enforced in application/service/repository layers. Database-level row-level security can be added before production if appropriate for the hosting model.

### Workers

Asynchronous workers process inbound events, AI jobs, notifications, SLA timers and daily analytics. Webhooks should acknowledge quickly and enqueue work instead of waiting for AI processing.

### AI service

AI is exposed through internal typed contracts. Agents do not directly mutate critical business state; they produce structured proposals that deterministic services validate and apply.

## Channel adapter abstraction

All channels normalize into a common internal event model:

```text
InboundEvent
- organization_id
- channel_type
- channel_account_id
- external_event_id
- external_message_id
- external_user_id
- conversation_key
- message_type
- text
- media[]
- source_timestamp
- raw_metadata
```

Outbound messages use a common interface:

```text
send_message(channel_account, recipient, message)
```

Each adapter handles provider-specific authentication, webhook verification, rate limits and payload formats.

## Identity model

`Customer` is the canonical person/company record. `CustomerIdentity` links one customer to a provider-specific identity such as a LINE user ID, WhatsApp phone/ID, Telegram user ID or email address.

Automatic identity merging must require confidence thresholds and should support manual review. Never merge identities solely because display names are equal.

## Security principles

- Secrets/tokens are stored in a dedicated secret store, not normal application tables.
- Encrypt data in transit and at rest where supported by infrastructure.
- Never log provider access tokens or sensitive message contents unnecessarily.
- Every request is tenant-scoped.
- RBAC is checked server-side.
- Sensitive changes produce audit events.
- Media should use private object storage with signed, short-lived access URLs.
- Retention/deletion policies must be configurable per organization and compatible with Thai PDPA requirements.

## Reliability

- Verify webhook signatures where provider supports them.
- Persist inbound event before processing.
- Use provider event/message IDs for idempotency.
- Retry transient provider/AI failures with backoff.
- Dead-letter failed jobs for operator review.
- Maintain channel health state and last successful webhook/message timestamp.

## Technology baseline

- Next.js / TypeScript
- Python / FastAPI
- PostgreSQL
- Redis-compatible queue/cache if required by worker implementation
- Object storage for attachments
- Docker for local development and reproducible deployment
- n8n may be used selectively for early workflow integrations, but core ticket/SLA logic remains in the application backend.
