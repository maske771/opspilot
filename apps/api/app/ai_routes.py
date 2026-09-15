import os
import uuid

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from .ai_intake import classify

router = APIRouter(prefix="/internal/ai", tags=["internal-ai"])


class IntakeRequest(BaseModel):
    text: str = Field(min_length=1, max_length=10000)


class IntakeResponse(BaseModel):
    category: str
    priority: str
    confidence: float
    reason: str
    request_id: uuid.UUID


def _check_internal_key(value: str | None) -> None:
    expected = os.getenv("INTERNAL_API_KEY")
    if expected:
        if value != expected:
            raise HTTPException(401, "Invalid internal API key")
    elif os.getenv("APP_ENV", "development") == "production":
        raise HTTPException(503, "INTERNAL_API_KEY is not configured")


@router.post("/intake", response_model=IntakeResponse)
def intake(payload: IntakeRequest, x_internal_api_key: str | None = Header(default=None)):
    _check_internal_key(x_internal_api_key)
    result = classify(payload.text)
    return IntakeResponse(
        category=result.category,
        priority=result.priority.value,
        confidence=result.confidence,
        reason=result.reason,
        request_id=uuid.uuid4(),
    )
