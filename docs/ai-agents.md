# AI Agents — MVP v0.1

## Design rule

AI produces structured proposals. Business-critical state transitions are validated by deterministic services.

## Intake Agent

### Input

- normalized inbound message
- recent conversation context
- customer/property/unit context when known

### Output

```json
{
  "intent": "maintenance_request",
  "category": "air_conditioning",
  "location": {
    "property_id": null,
    "unit": "304",
    "confidence": 0.98
  },
  "suggested_priority": "high",
  "priority_confidence": 0.96,
  "summary": "AC leaking in room 304",
  "language": "en",
  "requires_human_review": false
}
```

The output must conform to a strict JSON schema. Unknown values must be represented explicitly rather than hallucinated.

## Customer Match Agent

Returns candidate customer identities and confidence:

```json
{
  "matches": [
    {
      "customer_id": "uuid",
      "confidence": 0.94,
      "evidence": ["same external user id"]
    }
  ],
  "requires_human_review": false
}
```

Never merge customers only because their display names match.

## Response Agent

Generates channel-appropriate customer replies using the organization's tone and supported language. It must not promise compensation, refunds, legal outcomes or unsupported completion times without explicit system data.

## Image Proof Agent

Advisory only in MVP. Input: ticket context + uploaded image. Output:

```json
{
  "relevant": true,
  "confidence": 0.87,
  "observations": ["AC unit visible", "visible maintenance work"],
  "needs_human_review": false
}
```

It does not automatically close critical/high tickets.

## Analytics Agent

Consumes aggregated operational data and produces concise insights:

- volume changes
- category trends
- SLA anomalies
- vendor performance
- recurring issues

Insights should reference the underlying metric/date range so users can verify them.

## AI event logging

Every production AI call should record:

- agent type
- model identifier
- input hash/reference
- validated output
- confidence where available
- token/cost metadata where available
- timestamp

Do not store unnecessary sensitive prompt context in logs.
