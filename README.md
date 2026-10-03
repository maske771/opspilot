# OpsPilot

AI operations hub for property management, villas, serviced apartments and small hotels, with an initial focus on Thailand.

Customers write to the business in a messenger. OpsPilot recognizes what they need, opens a ticket against the right service and property, assigns an executor, tracks the SLA and keeps the customer informed — the customer only ever sees a normal conversation.

## Status

MVP running in production on a single VPS (branch `feat/mvp-foundation`). Every workflow step and screen named in [`docs/product-spec.md`](docs/product-spec.md) exists in some form; see its **Implementation status** section for what was built differently or is still missing.

Telegram is the only channel exercised against a real account. LINE, WhatsApp and Email adapters exist but have not been tested with real credentials.

## How a request flows

```text
Customer message (Telegram / LINE / WhatsApp / Email)
  → webhook (per-channel token, stored for idempotency)
  → customer matched or created
  → not linked to a property yet? bot asks for the property code first
  → service recognized from the organization's service catalog (keywords)
  → ticket: priority, SLA (property + service → organization → built-in), auto-assigned executor
  → reply to the customer (asks for a photo if none was sent)
  → staff notified in Telegram; SLA monitor warns and escalates
  → completion, manager approval for high/critical, close
  → dashboard, daily report (optionally pushed to Telegram), analytics
```

Details: [`docs/architecture.md`](docs/architecture.md).

## Stack

- **API**: Python 3.12, FastAPI, SQLAlchemy 2, PostgreSQL 17 — `apps/api`
- **Web**: Next.js (App Router, TypeScript), no CSS framework; UI in English, Russian and Thai with light/dark themes — `apps/web`
- **Background jobs**: in-process asyncio loops in the API (SLA monitor, daily report scheduler), each guarded by a Postgres advisory lock
- **Monitoring**: Prometheus, Alertmanager, Grafana, cAdvisor, postgres-exporter
- **Deployment**: Docker Compose on one VPS behind Caddy (automatic TLS)

## Repository layout

```text
apps/
  api/                  FastAPI backend (app/ and tests/)
  web/                  Next.js frontend
database/
  migrations/           numbered SQL migrations (001 … 018)
docs/                   product spec, architecture, API reference
monitoring/             Prometheus, Alertmanager and Grafana config used by docker-compose
infra/caddy/            Caddyfile.template, rendered into the production Caddyfile at deploy
scripts/deploy-prod.sh  production deploy
docker-compose.yml      local stack
docker-compose.prod.yml production stack
```

`infra/` also contains Prometheus/Alertmanager/Grafana folders that no compose file mounts — the live copies are under `monitoring/`.

## Local development

```bash
# Full stack (API, web, Postgres 17, monitoring)
docker compose up --build

# The local compose file does NOT apply migrations — load the schema once into the fresh database:
for f in database/migrations/*.sql; do docker compose exec -T db psql -U opspilot -d opspilot < "$f"; done

# Backend tests — need any Postgres; TEST_DATABASE_URL points at it (tests create their own tables)
cd apps/api
pip install -r requirements-dev.txt
TEST_DATABASE_URL=postgresql+psycopg://opspilot:opspilot_dev@localhost:5432/opspilot pytest tests/

# Frontend type-check and build
cd apps/web
npm install
npm run build
```

In production (`docker-compose.prod.yml`) a **fresh** database volume applies every file in `database/migrations` automatically. An existing database does not — apply each new migration by hand, before or right after deploying the code that needs it, or requests touching the changed tables fail with 500s.

## Documentation

- [`docs/product-spec.md`](docs/product-spec.md) — what the MVP is meant to do, plus implementation status
- [`docs/architecture.md`](docs/architecture.md) — how it is built today, and known deviations from the target design
- [`docs/api.md`](docs/api.md) — API reference, kept current with every change
- [`docs/api-dashboard.md`](docs/api-dashboard.md) — dashboard endpoint details
- [`docs/ai-agents.md`](docs/ai-agents.md) — what the "AI" parts actually do today, and the agent design they are meant to grow into
