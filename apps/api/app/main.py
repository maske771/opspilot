from fastapi import FastAPI
from pydantic import BaseModel, Field
from typing import Literal

app = FastAPI(title="OpsPilot API", version="0.1.0")


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


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "opspilot-api"}


@app.post("/internal/ai/intake", response_model=IntakeResponse)
def intake(request: IntakeRequest) -> IntakeResponse:
    """MVP intake contract.

    The first implementation is deterministic and intentionally conservative.
    It establishes the typed boundary that a real AI provider can implement later.
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
    priority = "critical" if any(w in text for w in critical_words) else "high" if any(w in text for w in high_words) else "medium"

    language = request.language or ("ru" if any("а" <= ch <= "я" for ch in text) else "en")
    location = Location(property_id=request.property_id, unit=request.unit, confidence=0.95 if request.unit else 0.0)
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
