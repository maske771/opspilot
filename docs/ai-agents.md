# AI agents

## Today: rule-based, no language model

No LLM is called anywhere yet. Each "agent" below is a deterministic baseline built so a model can replace it later without changing callers.

| Agent | What runs today | Module |
|---|---|---|
| Intake | Keyword match against the organization's **service catalog** (managed on the Services screen). The most severe matching service wins; nothing matched → "Other" for manual sorting. Greetings, thanks and short acknowledgements are recognized and don't open tickets. | `ai_intake.py`, `services.py` |
| Customer match | Exact identity lookup (channel + external user id), then normalized email/phone. Never by display name. | `customer_match.py` |
| Response | Templates in English and Russian: acknowledgement per service, follow-up and status answers, greetings, the property-code registration questions, and a request for a photo when none was sent. Language is detected from Cyrillic in the customer's messages. **Thai customers currently get English replies.** | `ai_response.py` |
| Image proof | Not implemented. | — |
| Analytics insights | Not implemented. The Analytics screen and daily report show computed metrics only. | — |

Business-critical decisions stay deterministic regardless: priority comes from the service, SLA from the property/organization settings, assignment from executor–service links and load.

### Internal endpoints

Service-to-service, protected by `INTERNAL_API_KEY` (required in production):

- `POST /internal/ai/intake` — classifies text with the **built-in default** rules. It has no organization context, so it does not see an organization's custom catalog; the webhook path does.
- `POST /internal/ai/customer-match`
- `POST /internal/ai/generate-response`

`analyze-image` and `daily-report` from the original plan don't exist yet.

## Target design

The rule that holds now and later: **AI produces structured proposals; deterministic services validate and apply them.** Agents never change ticket state, priority, SLA or permissions directly.

### Intake agent

Input: the normalized message, recent conversation, and the customer's property, unit and available services. Output, conforming to a strict JSON schema — unknown values are explicit, never invented:

```json
{
  "intent": "maintenance_request",
  "service_code": "hvac",
  "location": { "property_id": null, "unit": "304", "confidence": 0.98 },
  "suggested_priority": "high",
  "priority_confidence": 0.96,
  "summary": "AC leaking in room 304",
  "language": "en",
  "requires_human_review": false
}
```

The service must come from the organization's catalog (and the property's services when known); anything else falls back to manual sorting.

### Customer match agent

Returns candidate identities with confidence and evidence; merging below a confidence threshold goes to human review. Never merge on matching display names.

### Response agent

Channel-appropriate replies in the customer's language (EN/RU/TH) and the organization's tone. Must not promise compensation, refunds, legal outcomes or completion times not backed by system data.

### Image proof agent

Advisory only: is the completion photo relevant to the ticket. Never closes high/critical tickets by itself — those still need manager approval.

### Analytics agent

Short insights over aggregated data (volume changes, service trends, SLA anomalies, recurring issues), each referencing the metric and date range so users can verify it.

### Logging every AI call

Agent type, model id, input reference/hash, validated output, confidence, token/cost metadata, timestamp. No unnecessary sensitive prompt content in logs.
