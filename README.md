# OpsPilot

AI Operations Hub for property management, villas, serviced apartments and small hotels in Thailand.

## MVP v0.1

Core workflow:

`LINE / WhatsApp / Telegram / Email -> Unified Inbox -> AI Intake -> Ticket -> Assignment -> SLA -> Completion -> Analytics`

### Product principles

- Multi-channel from day one.
- Connect existing customer communication accounts where supported; allow assisted creation of new business channels.
- Email-only businesses are supported.
- Customer identity is separated from channel identity so conversations across channels can map to one customer.
- Multi-tenant SaaS architecture with strict organization-level data isolation.
- AI assists classification, communication and analytics; deterministic business rules control priority, SLA, permissions and sensitive actions.
- Maintenance is the first use case; architecture is designed to expand into guest requests, complaints, housekeeping, vendors and sales operations.

## Planned stack

- Web: Next.js
- API: Python / FastAPI
- Database: PostgreSQL
- Background jobs: queue/worker architecture
- Automation: n8n where useful during MVP
- Channels: LINE Messaging API, WhatsApp Business Platform, Telegram Bot API, Email

## Repository structure

```text
apps/
  web/                  # Next.js frontend
  api/                  # FastAPI backend
packages/
  shared/               # Shared contracts/types
services/
  ai/                   # AI agents and schemas
  channels/             # Channel adapters
  workers/              # Async jobs
 database/
  migrations/
  seeds/
docs/
  product-spec.md
  architecture.md
  api.md
  ai-agents.md
```

## Test Center

Test runs and individual pytest results are stored in PostgreSQL and available in the web UI at `/tests`.

Local setup after pulling this feature branch:

```powershell
docker compose up -d db api
Get-Content .\database\migrations\005_test_center.sql | docker compose exec -T db psql -U opspilot -d opspilot
docker compose build api
docker compose up -d --force-recreate api
```

To publish a local pytest report:

```powershell
cd .\apps\api
pytest -q tests --junitxml=..\..\test-results.xml
cd ..\..
python .\scripts\publish_pytest_report.py .\test-results.xml
```

The API also publishes CI pytest results automatically after a successful GitHub Actions run.

## Status

Foundation phase. Product and MVP specification are being implemented incrementally.
