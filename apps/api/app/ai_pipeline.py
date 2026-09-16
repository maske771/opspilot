from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from .ai_intake import classify
from .ai_response import GeneratedResponse, get_response_generator
from .customer_match import CustomerMatch, find_customer


@dataclass(frozen=True)
class AIPipelineResult:
    category: str
    priority: str
    intake_confidence: float
    intake_reason: str
    customer_id: Any | None
    customer_match_type: str
    customer_match_confidence: float
    response: GeneratedResponse


def process_message(
    db: Session,
    organization_id,
    *,
    text: str,
    channel_type: str,
    external_user_id: str,
    email: str | None = None,
    phone: str | None = None,
) -> AIPipelineResult:
    intake = classify(text)
    match: CustomerMatch = find_customer(
        db,
        organization_id,
        channel_type=channel_type,
        external_user_id=external_user_id,
        email=email,
        phone=phone,
    )
    response = get_response_generator().generate(
        customer_message=text,
        category=intake.category,
        priority=intake.priority.value,
    )
    return AIPipelineResult(
        category=intake.category,
        priority=intake.priority.value,
        intake_confidence=intake.confidence,
        intake_reason=intake.reason,
        customer_id=match.customer.id if match.customer else None,
        customer_match_type=match.match_type,
        customer_match_confidence=match.confidence,
        response=response,
    )
