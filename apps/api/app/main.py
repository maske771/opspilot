from datetime import datetime, timedelta, timezone
from os import getenv
from typing import Literal
from uuid import UUID

import psycopg
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

app = FastAPI(title="OpsPilot API", version="0.2.0")

DATABASE_URL = getenv(
    "DATABASE_URL",
    "postgresql://opspilot:opspilot_dev@localhost:5432/opspilot",
)

SLA_MINUTES = {
    "critical": (15, 60),
    "high": (30, 240),
    "medium": (120, 1440),
    "low": (480, 4320),
}


class Location(BaseModel):
    property_id: str | None = None
    unit: str | None = None
    confidence: float = Field(ge=0, le=1)


class IntakeRequest(BaseModel):
    text: str = Field(min_length=1)
    language: str | None = None
    conversation_context: list[str] = Field(default_factory=list)
    property_id: str | None = None
    unit: str | None = None


class IntakeResponse(BaseModel):
    intent: Literal["maintenance_request", "other"]
    category: Literal[
        "air_conditioning", "plumbing", "electrical", "internet_wifi",
        "appliance", "furniture", "cleaning", "security", "other"
    ]
    location: Location
    suggested_priority: Literal["critical", "high", "medium", "low"]
    priority_confidence: float = Field(ge=0, le=1)
    summary: str
    language: str
    requires_human_review: bool


class TicketFromIntakeRequest(IntakeRequest):
    organization_id: UUID


class TicketResponse(BaseModel):
    id: UUID
    organization_id: UUID
    property_id: UUID | None
    unit_id: UUID | None
    category: str
    priority: str
    status: str
    summary: str
    response_due_at: datetime
    resolution_due_at: datetime
    requires_human_review: bool


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "opspilot-api"}


def classify_intake(request: IntakeRequest) -> IntakeResponse:
    """Deterministic MVP intake classifier.

    The typed contract is intentionally stable so a real AI provider can replace
    this classifier without changing the downstream ticket/SLA interface.
    """
    text = request.text.lower()

    rules = [
        (("aircon", "air con", "air conditioning", "ac ", " кондиционер", "кондиционер"), "air_conditioning"),
        (("leak", "water", "pipe", "plumb", "протеч", "вода", "сантех"), "plumbing"),
        (("electric", "power", "socket", "light", "электр", "розет", "свет"), "electrical"),
        (("wifi", "wi-fi", "internet", "интернет", "вайфай"), "internet_wifi"),
        (("fridge", "refrigerator", "washing machine", "oven", "холодиль", "стирал", "посудомо"), "appliance"),
        (("furniture", "chair", "table", "bed", "мебел", "стул", "стол", "кровать"), "furniture"),
        (("clean", "cleaning", "гряз", "уборк"), "cleaning"),
        (("security", "lock", "key", "alarm", "безопас", "замок", "ключ"), "security"),
    ]

    category = "other"
    for keywords, candidate in rules:
        if any(keyword in text for keyword in keywords):
            category = candidate
            break

    critical_words = ("fire", "flood", "gas", "danger", "emergency", "пожар", "газ", "опас", "авар")
    high_words = ("urgent", "asap", "leaking", "broken", "не работает", "срочно", "протекает")
    priority = (
        "critical" if any(w in text for w in critical_words)
        else "high" if any(w in text for w in high_words)
        else "medium"
    )

    language = request.language or ("ru" if any("а" <= ch <= "я" for ch in text) else "en")
    location = Location(
        property_id=request.property_id,
        unit=request.unit,
        confidence=0.95 if request.unit else 0.0,
    )
    return IntakeResponse(
        intent="maintenance_request" if category != "other" else "other",
        category=category,
        location=location,
        suggested_priority=priority,
        priority_confidence=0.90 if priority in ("critical", "high") else 0.70,
        summary=request.text.strip()[:200],
        language=language,
        requires_human_review=category == "other" or priority == "critical",
    )


@app.post("/internal/ai/intake", response_model=IntakeResponse)
def intake(request: IntakeRequest) -> IntakeResponse:
    return classify_intake(request)


@app.post("/internal/tickets/from-intake", response_model=TicketResponse)
def create_ticket_from_intake(request: TicketFromIntakeRequest) -> TicketResponse:
    result = classify_intake(request)
    now = datetime.now(timezone.utc)
    response_minutes, resolution_minutes = SLA_MINUTES[result.suggested_priority]
    response_due = now + timedelta(minutes=response_minutes)
    resolution_due = now + timedelta(minutes=resolution_minutes)

    property_id = None
    unit_id = None

    try:
        with psycopg.connect(DATABASE_URL) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id FROM properties WHERE id = %s AND organization_id = %s",
                    (request.property_id, request.organization_id),
                )
                property_row = cur.fetchone() if request.property_id else None
                if request.property_id and not property_row:
                    raise HTTPException(status_code=400, detail="property_id not found in organization")
                property_id = UUID(str(property_row[0])) if property_row else None

                if request.unit:
                    cur.execute(
                        "SELECT id FROM units WHERE name = %s AND organization_id = %s"
                        " AND (%s IS NULL OR property_id = %s)",
                        (request.unit, request.organization_id, request.property_id, request.property_id),
                    )
                    unit_row = cur.fetchone()
                    if not unit_row:
                        raise HTTPException(status_code=400, detail="unit not found in organization")
                    unit_id = UUID(str(unit_row[0]))

                cur.execute(
                    """INSERT INTO tickets (
                        organization_id, property_id, unit_id, category, priority,
                        status, summary, response_due_at, resolution_due_at
                    ) VALUES (%s, %s, %s, %s, %s, 'open', %s, %s, %s)
                    RETURNING id""",
                    (
                        request.organization_id,
                        property_id,
                        unit_id,
                        result.category,
                        result.suggested_priority,
                        result.summary,
                        response_due,
                        resolution_due,
                    ),
                )
                ticket_id = cur.fetchone()[0]
    except psycopg.Error as exc:
        raise HTTPException(status_code=503, detail=f"database error: {exc}") from exc

    return TicketResponse(
        id=ticket_id,
        organization_id=request.organization_id,
        property_id=property_id,
        unit_id=unit_id,
        category=result.category,
        priority=result.suggested_priority,
        status="open",
        summary=result.summary,
        response_due_at=response_due,
        resolution_due_at=resolution_due,
        requires_human_review=result.requires_human_review,
    )
