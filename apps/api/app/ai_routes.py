import os
import uuid

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .ai_intake import classify
from .ai_response import generate_with_fallback
from .customer_match import find_customer
from .db import get_db

router = APIRouter(prefix="/internal/ai", tags=["internal-ai"])


class IntakeRequest(BaseModel):
    text: str = Field(min_length=1, max_length=10000)


class IntakeResponse(BaseModel):
    category: str
    priority: str
    confidence: float
    reason: str
    request_id: uuid.UUID


class CustomerMatchRequest(BaseModel):
    organization_id: uuid.UUID
    channel_type: str = Field(min_length=1, max_length=50)
    external_user_id: str = Field(min_length=1, max_length=255)
    email: str | None = Field(default=None, max_length=320)
    phone: str | None = Field(default=None, max_length=50)


class CustomerMatchResponse(BaseModel):
    customer_id: uuid.UUID | None
    match_type: str
    confidence: float
    request_id: uuid.UUID


class GenerateResponseRequest(BaseModel):
    customer_message: str = Field(min_length=1, max_length=10000)
    category: str = Field(min_length=1, max_length=100)
    priority: str = Field(min_length=1, max_length=30)


class GenerateResponseResponse(BaseModel):
    text: str
    provider: str
    confidence: float
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


@router.post("/customer-match", response_model=CustomerMatchResponse)
def customer_match(
    payload: CustomerMatchRequest,
    x_internal_api_key: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    _check_internal_key(x_internal_api_key)
    result = find_customer(
        db,
        payload.organization_id,
        channel_type=payload.channel_type,
        external_user_id=payload.external_user_id,
        email=payload.email,
        phone=payload.phone,
    )
    return CustomerMatchResponse(
        customer_id=result.customer.id if result.customer else None,
        match_type=result.match_type,
        confidence=result.confidence,
        request_id=uuid.uuid4(),
    )


@router.post("/generate-response", response_model=GenerateResponseResponse)
def generate_response(
    payload: GenerateResponseRequest,
    x_internal_api_key: str | None = Header(default=None),
):
    _check_internal_key(x_internal_api_key)
    result = generate_with_fallback(
        customer_message=payload.customer_message,
        category=payload.category,
        priority=payload.priority,
    )
    return GenerateResponseResponse(
        text=result.text,
        provider=result.provider,
        confidence=result.confidence,
        request_id=uuid.uuid4(),
    )
