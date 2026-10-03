import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .audit import record
from .auth import get_current_user
from .db import get_db
from .models import Service, TicketPriority, User, UserRole
from .notifications import SUPPORTED_LANGUAGES
from .services import ensure_services, new_service_code, remove_code_from_specialties

router = APIRouter(prefix="/services", tags=["services"])


class ServiceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    code: str
    names: dict[str, str]
    keywords: list[str]
    default_priority: TicketPriority
    is_system: bool
    archived: bool
    position: int


def _clean_names(value: dict[str, str] | None) -> dict[str, str] | None:
    if value is None:
        return None
    cleaned = {}
    for lang, name in value.items():
        if lang not in SUPPORTED_LANGUAGES:
            raise ValueError(f"language must be one of {', '.join(SUPPORTED_LANGUAGES)}")
        name = (name or "").strip()
        if len(name) > 100:
            raise ValueError("a service name can be at most 100 characters")
        if name:
            cleaned[lang] = name
    if not cleaned:
        raise ValueError("a service needs a name in at least one language")
    return cleaned


def _clean_keywords(value: list[str] | None) -> list[str] | None:
    if value is None:
        return None
    seen: list[str] = []
    for keyword in value:
        keyword = keyword.strip().lower()
        if len(keyword) > 100:
            raise ValueError("a keyword can be at most 100 characters")
        if keyword and keyword not in seen:
            seen.append(keyword)
    return seen


class _ServiceFields(BaseModel):
    @field_validator("names", check_fields=False)
    @classmethod
    def _valid_names(cls, value):
        return _clean_names(value)

    @field_validator("keywords", check_fields=False)
    @classmethod
    def _valid_keywords(cls, value):
        return _clean_keywords(value)


class ServiceCreate(_ServiceFields):
    names: dict[str, str]
    keywords: list[str] = Field(default_factory=list, max_length=200)
    default_priority: TicketPriority = TicketPriority.MEDIUM


class ServiceUpdate(_ServiceFields):
    names: dict[str, str] | None = None
    keywords: list[str] | None = Field(default=None, max_length=200)
    default_priority: TicketPriority | None = None


def _require_admin(user: User) -> None:
    if user.role not in (UserRole.OWNER, UserRole.ADMIN):
        raise HTTPException(status_code=403, detail="Only owner or admin can change the service catalog")


def _get_service(db: Session, user: User, service_id: uuid.UUID) -> Service:
    service = db.get(Service, service_id)
    if service is None or service.organization_id != user.organization_id:
        raise HTTPException(404, "Service not found")
    return service


@router.get("", response_model=list[ServiceRead])
def list_services(include_archived: bool = False, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ensure_services(db, user.organization_id)
    db.commit()
    stmt = select(Service).where(Service.organization_id == user.organization_id)
    if not include_archived:
        stmt = stmt.where(Service.archived.is_(False))
    return list(db.scalars(stmt.order_by(Service.position, Service.created_at)).all())


@router.post("", response_model=ServiceRead, status_code=201)
def create_service(payload: ServiceCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _require_admin(user)
    ensure_services(db, user.organization_id)
    last = db.scalar(
        select(func.max(Service.position)).where(Service.organization_id == user.organization_id, Service.is_system.is_(False))
    ) or 0
    service = Service(
        organization_id=user.organization_id,
        code=new_service_code(),
        names=payload.names,
        keywords=payload.keywords,
        default_priority=payload.default_priority,
        position=last + 1,
    )
    db.add(service)
    # Keep the fallback service at the bottom of the list.
    for system in db.scalars(select(Service).where(Service.organization_id == user.organization_id, Service.is_system.is_(True))):
        system.position = last + 2
    db.commit()
    db.refresh(service)
    return service


@router.patch("/{service_id}", response_model=ServiceRead)
def update_service(service_id: uuid.UUID, payload: ServiceUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _require_admin(user)
    service = _get_service(db, user, service_id)
    changes = payload.model_dump(exclude_unset=True, exclude_none=True)
    if service.is_system and changes.get("keywords"):
        raise HTTPException(400, "The fallback service catches everything unrecognized and has no keywords")
    for field, value in changes.items():
        setattr(service, field, value)
    db.commit()
    db.refresh(service)
    return service


@router.delete("/{service_id}", status_code=204)
def archive_service(service_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Archived, not deleted: existing tickets still point at the service's code and need its name."""
    _require_admin(user)
    service = _get_service(db, user, service_id)
    if service.is_system:
        raise HTTPException(400, "The fallback service can't be removed")
    service.archived = True
    record(db, organization_id=service.organization_id, actor=user, entity_type="service", entity_id=service.id, action="archived", details={"code": service.code, "names": service.names})
    remove_code_from_specialties(db, user.organization_id, service.code)
    db.commit()
