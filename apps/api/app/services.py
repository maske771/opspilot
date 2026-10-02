import secrets
import uuid

from sqlalchemy import any_, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from .ai_intake import DEFAULT_RULES, FALLBACK_CODE, ServiceRule
from .models import Service, TicketPriority, User

DEFAULT_NAMES = {
    "emergency": {"en": "Emergency", "ru": "Авария", "th": "เหตุฉุกเฉิน"},
    "plumbing": {"en": "Plumbing", "ru": "Сантехника", "th": "ระบบประปา"},
    "electrical": {"en": "Electrical", "ru": "Электрика", "th": "ระบบไฟฟ้า"},
    "hvac": {"en": "HVAC", "ru": "Кондиционирование", "th": "เครื่องปรับอากาศ"},
    "appliance": {"en": "Appliances", "ru": "Техника", "th": "เครื่องใช้ไฟฟ้า"},
    "access": {"en": "Access & keys", "ru": "Доступ и ключи", "th": "กุญแจและการเข้าออก"},
    FALLBACK_CODE: {"en": "Other", "ru": "Другое", "th": "อื่น ๆ"},
}


def ensure_services(db: Session, organization_id: uuid.UUID) -> None:
    """Seed the default catalog the first time an organization's services are needed. The fallback
    service can't be deleted, so once seeded an organization never drops back to zero services."""
    if db.scalar(select(func.count(Service.id)).where(Service.organization_id == organization_id)):
        return
    rows = [
        dict(
            organization_id=organization_id,
            code=rule.code,
            names=DEFAULT_NAMES[rule.code],
            keywords=list(rule.keywords),
            default_priority=rule.priority,
            position=position,
        )
        for position, rule in enumerate(DEFAULT_RULES)
    ]
    rows.append(
        dict(
            organization_id=organization_id,
            code=FALLBACK_CODE,
            names=DEFAULT_NAMES[FALLBACK_CODE],
            keywords=[],
            default_priority=TicketPriority.MEDIUM,
            is_system=True,
            position=len(rows),
        )
    )
    # Two webhooks for a brand-new organization can race here; the unique (organization_id, code)
    # constraint plus DO NOTHING keeps the second one harmless.
    db.execute(insert(Service).values(rows).on_conflict_do_nothing(constraint="uq_services_org_code"))
    db.flush()


def active_services(db: Session, organization_id: uuid.UUID) -> list[Service]:
    ensure_services(db, organization_id)
    return list(
        db.scalars(
            select(Service).where(Service.organization_id == organization_id, Service.archived.is_(False)).order_by(Service.position, Service.created_at)
        ).all()
    )


def intake_rules(db: Session, organization_id: uuid.UUID) -> tuple[list[ServiceRule], TicketPriority]:
    """Keyword rules for the classifier, plus the priority to use when nothing matches (the
    fallback service's own default priority)."""
    services = active_services(db, organization_id)
    rules = [ServiceRule(s.code, tuple(s.keywords or ()), s.default_priority) for s in services if not s.is_system]
    fallback = next((s for s in services if s.code == FALLBACK_CODE), None)
    return rules, fallback.default_priority if fallback else TicketPriority.MEDIUM


def new_service_code() -> str:
    return "svc_" + secrets.token_hex(4)


def remove_code_from_specialties(db: Session, organization_id: uuid.UUID, code: str) -> None:
    for user in db.scalars(select(User).where(User.organization_id == organization_id, any_(User.specialties) == code)):
        user.specialties = [s for s in user.specialties if s != code]
