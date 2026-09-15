import re
import uuid
from dataclasses import dataclass

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from .models import Customer, CustomerIdentity


@dataclass(frozen=True)
class CustomerMatch:
    customer: Customer | None
    match_type: str
    confidence: float


def normalize_email(value: str | None) -> str | None:
    if not value:
        return None
    value = value.strip().lower()
    return value or None


def normalize_phone(value: str | None) -> str | None:
    if not value:
        return None
    digits = re.sub(r"\D", "", value)
    if not digits:
        return None
    # Treat Russian local 8-prefix and international +7 as the same number.
    if len(digits) == 11 and digits.startswith("8"):
        digits = "7" + digits[1:]
    return digits


def find_customer(
    db: Session,
    organization_id: uuid.UUID,
    *,
    channel_type: str,
    external_user_id: str,
    email: str | None = None,
    phone: str | None = None,
) -> CustomerMatch:
    identity = db.scalar(
        select(CustomerIdentity).where(
            CustomerIdentity.organization_id == organization_id,
            CustomerIdentity.channel_type == channel_type,
            CustomerIdentity.external_user_id == external_user_id,
        )
    )
    if identity:
        customer = db.get(Customer, identity.customer_id)
        return CustomerMatch(customer, "identity", 1.0)

    normalized_email = normalize_email(email)
    if normalized_email:
        customer = db.scalar(
            select(Customer).where(
                Customer.organization_id == organization_id,
                Customer.email.is_not(None),
                Customer.email == normalized_email,
            )
        )
        if customer:
            return CustomerMatch(customer, "email", 0.98)

    normalized_phone = normalize_phone(phone)
    if normalized_phone:
        candidates = db.scalars(
            select(Customer).where(
                Customer.organization_id == organization_id,
                Customer.phone.is_not(None),
            )
        ).all()
        for customer in candidates:
            if normalize_phone(customer.phone) == normalized_phone:
                return CustomerMatch(customer, "phone", 0.97)

    return CustomerMatch(None, "new", 0.0)
