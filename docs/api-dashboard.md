# Dashboard API

## GET /dashboard/summary

Returns tenant-scoped operational KPIs for the authenticated user's organization.

Authentication: `Authorization: Bearer <access_token>`.

### Response

```json
{
  "tickets_total": 12,
  "tickets_open": 8,
  "tickets_overdue": 2,
  "customers_total": 25,
  "properties_total": 4,
  "units_total": 86,
  "tickets_by_status": [
    {"status": "new", "count": 3},
    {"status": "assigned", "count": 2},
    {"status": "accepted", "count": 1},
    {"status": "in_progress", "count": 2},
    {"status": "completed", "count": 2},
    {"status": "waiting_approval", "count": 1},
    {"status": "closed", "count": 1}
  ],
  "tickets_by_priority": [
    {"priority": "critical", "count": 1},
    {"priority": "high", "count": 4},
    {"priority": "medium", "count": 5},
    {"priority": "low", "count": 2}
  ]
}
```

### Rules

- Results are always filtered by the authenticated user's `organization_id`.
- `tickets_open` includes `new`, `assigned`, `accepted`, `in_progress`, and `waiting_approval`.
- `tickets_overdue` counts non-closed tickets whose `resolution_deadline` has passed.
- Status and priority arrays always contain every supported enum value, with zero counts when unused.
- No organization ID is accepted from the client, preventing cross-tenant dashboard access.
