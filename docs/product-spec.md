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
