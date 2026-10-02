import secrets
import uuid

from sqlalchemy import any_, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from .ai_intake import DEFAULT_RULES, FALLBACK_CODE, ServiceRule
from .models import Organization, PropertyService, Service, TicketPriority, User

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


def intake_rules(db: Session, organization_id: uuid.UUID, property_id: uuid.UUID | None = None) -> tuple[list[ServiceRule], TicketPriority]:
    """Keyword rules for the classifier, plus the priority to use when nothing matches (the
    fallback service's own default priority). With a configured property, only the services that
    property gets are considered — a request for anything else falls back to manual sorting."""
    services = active_services(db, organization_id)
    if property_id is not None:
        offered = set(db.scalars(select(PropertyService.service_id).where(PropertyService.property_id == property_id)))
        if offered:
            services = [s for s in services if s.id in offered or s.is_system]
    rules = [ServiceRule(s.code, tuple(s.keywords or ()), s.default_priority) for s in services if not s.is_system]
    fallback = next((s for s in services if s.code == FALLBACK_CODE), None)
    return rules, fallback.default_priority if fallback else TicketPriority.MEDIUM


def sla_overrides_for(db: Session, organization_id: uuid.UUID, property_id: uuid.UUID | None, service_code: str) -> dict:
    """SLA overrides for a ticket, per priority: the property+service setting wins, then the
    organization's, then (in sla.calculate_sla) the built-in default."""
    org = db.get(Organization, organization_id)
    merged = dict((org.sla_overrides if org else None) or {})
    if property_id is not None:
        property_sla = db.scalar(
            select(PropertyService.sla)
            .join(Service, Service.id == PropertyService.service_id)
            .where(PropertyService.property_id == property_id, Service.organization_id == organization_id, Service.code == service_code)
        )
        merged.update(property_sla or {})
    return merged


def new_service_code() -> str:
    return "svc_" + secrets.token_hex(4)


def remove_code_from_specialties(db: Session, organization_id: uuid.UUID, code: str) -> None:
    for user in db.scalars(select(User).where(User.organization_id == organization_id, any_(User.specialties) == code)):
        user.specialties = [s for s in user.specialties if s != code]
