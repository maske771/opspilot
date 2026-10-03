# Product Specification — MVP v0.1

## Positioning

**OpsPilot — AI Operations Hub for Property Management.**

The product connects to the communication channels a business already uses and turns incoming requests into structured, trackable operational work.

## Initial ICP

- Property management companies
- Villa management companies
- Serviced apartments
- Small hotels / boutique hospitality businesses
- Small condo operations teams

Initial geographic focus: Thailand, with LINE as a key channel but without making the product LINE-dependent.

## Core promise

> Every request gets an owner, deadline and follow-up.

## MVP workflow

1. Customer sends a request through LINE, WhatsApp, Telegram or Email.
2. Channel adapter validates and normalizes the inbound event.
3. Customer identity is matched or created.
4. AI Intake extracts intent, category, location, language and suggested priority.
5. Deterministic business rules calculate final priority and SLA.
6. Ticket is created or an existing ticket is updated.
7. Assignment engine selects a staff member or vendor.
8. Customer receives acknowledgement.
9. Staff receives the work order through the configured channel.
10. SLA worker monitors response and resolution deadlines.
11. Staff marks work complete and can attach photos/comments.
12. Manager can approve closure for high/critical tickets.
13. Daily operations summary is generated for management.

## Supported channels in MVP

- LINE
- WhatsApp Business
- Telegram
- Email

Channel management must support:

- connect an existing account where official APIs permit it;
- assisted setup for a new business account/bot/mailbox;
- disconnect/reconnect;
- health/status checks;
- channel-specific routing rules.

Personal messaging accounts must not be connected through unofficial scraping, browser automation or protocol emulation. Where a provider requires a business account for automation, the UI must explain this and guide the customer through the official setup path.

## User roles

- Owner
- Admin
- Manager
- Staff
- Technician

Customers/residents/guests do not need an OpsPilot login for MVP.

## MVP screens

### Onboarding

- Registration
- Company setup
- Channel selection
- Channel connection center
- Property setup
- CSV/XLSX import preparation
- Team setup
- Recommended SLA setup
- Test request
- Go Live

### Main application

- Dashboard
- Unified Inbox
- Ticket list
- Ticket detail / conversation timeline
- Properties
- Team
- Channels
- Analytics
- Settings

## Dashboard requirements

Owner should understand operational health within approximately 10 seconds. Show:

- Open tickets
- In-progress tickets
- Overdue tickets
- Critical tickets
- Recent requests
- SLA performance
- AI insights

## Unified Inbox

One conversation view across all connected channels. A customer may have identities in multiple channels; the UI should present them as one customer when identity matching is sufficiently confident.

## Ticket

A ticket is the central operational object. It contains:

- customer
- property
- unit/location
- originating conversation
- category
- priority
- status
- assignee/vendor
- response SLA
- resolution SLA
- messages
- attachments
- work logs
- AI analysis
- audit history

## AI boundaries

AI may:

- detect language
- classify intent/category
- summarize
- match customer identities with confidence
- draft customer responses
- analyze operational trends
- analyze proof-of-work images as an advisory signal

Deterministic rules must control:

- final priority
- SLA calculation
- authorization/RBAC
- sensitive status changes
- deletion
- financial/legal actions

High/critical closure should require human approval in MVP.

## Initial categories

- Air conditioning
- Plumbing
- Electrical
- Internet/Wi-Fi
- Appliance
- Furniture
- Cleaning
- Security
- Other

## Initial SLA defaults

| Priority | Response | Resolution |
|---|---:|---:|
| Critical | 15 min | 1 hour |
| High | 30 min | 4 hours |
| Medium | 2 hours | 24 hours |
| Low | 8 hours | 72 hours |

All values are configurable per organization.

## Out of scope for MVP

- Payments/accounting
- Booking engine/PMS replacement
- Marketplace
- Native mobile app
- Predictive maintenance
- Voice calls
- Deep ERP/PMS integrations

## Pilot success criteria

A real pilot customer must be able to complete the full lifecycle:

Customer message -> normalized event -> customer match -> ticket -> assignment -> staff notification -> SLA tracking -> completion -> optional photo -> manager approval -> closure -> management report.

Target: 3 pilot customers before expanding scope.

---

## Implementation status (as of 2026-10-03)

The specification above is kept as written. This section records what has been built, what was built differently, and what is still missing. Architecture details: [`architecture.md`](architecture.md); API: [`api.md`](api.md).

### MVP workflow

| # | Step | Status |
|---|---|---|
| 1 | Request through LINE, WhatsApp, Telegram or Email | Built for all four. **Only Telegram has been tested with a real account.** |
| 2 | Adapter validates and normalizes | Built. Webhooks authenticate per channel; raw events stored for idempotency. |
| 3 | Customer identity matched or created | Built. New: on first contact the bot asks for a **property code** and links the customer to that property; afterwards only managers change it. |
| 4 | AI intake: intent, category, location, language, priority | Rule-based, no LLM: keywords from a configurable **service catalog**; language detection is EN/RU only. Location comes from the customer's property link, not from the message text. |
| 5 | Deterministic priority and SLA | Built. Priority from the service; SLA per priority resolved as property+service → organization → built-in defaults. |
| 6 | Ticket created or updated | Built. Further messages while a ticket is open are added to it. |
| 7 | Assignment to staff or vendor | Staff/technicians linked to services, least-loaded wins. **Vendors are not modeled.** |
| 8 | Customer acknowledgement | Built, EN/RU templates; asks for a photo when none was sent. **Thai customers get English.** |
| 9 | Staff receive the work order in their channel | Built for Telegram (staff link their account from their profile). |
| 10 | SLA worker | Built: due-soon, overdue and escalation notices. |
| 11 | Staff complete work with photos/comments | **Yes.** The ticket's Work log tab takes comments and up to 5 photos per entry; customer photos from the chat are stored and shown too. |
| 12 | Manager approval for high/critical | Built. |
| 13 | Daily operations summary | Built: page plus optional Telegram delivery with schedule, timezone, skipped days and a custom template. |

### Screens

| Spec | Status |
|---|---|
| Onboarding (10 screens) | One 7-step wizard: company, channel, property, team, SLA (view only), test request, go live. **CSV/XLSX import not built.** |
| Dashboard | Built: totals and breakdowns. "Recent requests" and "AI insights" are not on it; recent requests live in the Inbox. |
| Unified Inbox | Built, one row per conversation. Customers with identities in several channels are matched to one customer, but the Inbox doesn't merge their conversations into one view. |
| Tickets, ticket detail | Built (timeline, photos, manual replies signed with the staff member's name). |
| Properties | Built, plus units, resident code, and per-property services and SLA. |
| Team | Built, plus executor ↔ service links. |
| Channels | Built: connect, credentials, token rotation, Telegram webhook registration. No health checks. |
| Analytics | Built: volume, response/resolution SLA compliance, breakdowns by service/property/staff. |
| Settings | Built: company name, organization SLA. Services have their own screen. |

### Other differences from the spec

- **Categories → service catalog.** The fixed list in "Initial categories" became a per-organization catalog managed in the UI. It starts with Emergency, Plumbing, Electrical, HVAC, Appliances, Access & keys and Other; Internet/Wi-Fi, Furniture, Cleaning and Security can be added as services.
- **SLA defaults** match the table above and are configurable per organization and per property+service.
- **Ticket fields not built:** vendor, AI analysis. Audit history is built: the ticket's History tab and an organization-wide Audit log screen for owner/admin.
- **AI** is rule-based throughout; see [`ai-agents.md`](ai-agents.md).
- **Additions not in the spec:** staff Telegram notifications and escalations, daily-report push delivery, property resident codes, UI in English/Russian/Thai with light and dark themes.

### Pilot readiness

The pilot lifecycle runs end to end on Telegram, including completion comments and photos (step 11).
