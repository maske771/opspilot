import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .auth import get_current_user
from .db import get_db
from .models import Organization, Property, PropertyService, Service, TicketPriority, User, UserRole
from .organization_routes import SlaPair
from .services import active_services
from .sla import SLA_MINUTES

router = APIRouter(prefix="/properties", tags=["property-services"])


class EffectivePropertySla(BaseModel):
    priority: TicketPriority
    response_minutes: int
    resolution_minutes: int
    source: Literal["property", "organization", "default"]


class PropertyServiceRead(BaseModel):
    service_id: uuid.UUID
    code: str
    names: dict[str, str]
    is_system: bool
    enabled: bool
    sla: list[EffectivePropertySla]
    overrides: dict[TicketPriority, SlaPair]  # only what's set on this property, for editing


class PropertyServicesRead(BaseModel):
    configured: bool  # False: nothing set up yet, every service is offered with the organization's SLA
    services: list[PropertyServiceRead]


class PropertyServiceEntry(BaseModel):
    service_id: uuid.UUID
    sla: dict[TicketPriority, SlaPair] = Field(default_factory=dict)


class PropertyServicesUpdate(BaseModel):
    # The full list of services offered at the property. Empty resets it to "not configured".
    services: list[PropertyServiceEntry] = Field(max_length=500)


def _require_admin(user: User) -> None:
    if user.role not in (UserRole.OWNER, UserRole.ADMIN):
        raise HTTPException(status_code=403, detail="Only owner or admin can configure property services and SLA")


def _get_property(db: Session, user: User, property_id: uuid.UUID) -> Property:
    item = db.get(Property, property_id)
    if item is None or item.organization_id != user.organization_id:
        raise HTTPException(404, "Property not found")
    return item


def _read(db: Session, item: Property) -> PropertyServicesRead:
    org = db.get(Organization, item.organization_id)
    org_overrides = (org.sla_overrides if org else None) or {}
    rows = {r.service_id: r for r in db.scalars(select(PropertyService).where(PropertyService.property_id == item.id))}
    configured = bool(rows)
    result = []
    for service in active_services(db, item.organization_id):
        row = rows.get(service.id)
        property_overrides = (row.sla if row else None) or {}
        sla = []
        for priority, (default_response, default_resolution) in SLA_MINUTES.items():
            if priority.value in property_overrides:
                pair, source = property_overrides[priority.value], "property"
            elif priority.value in org_overrides:
                pair, source = org_overrides[priority.value], "organization"
            else:
                pair, source = {"response_minutes": default_response, "resolution_minutes": default_resolution}, "default"
            sla.append(EffectivePropertySla(priority=priority, response_minutes=pair["response_minutes"], resolution_minutes=pair["resolution_minutes"], source=source))
        result.append(
            PropertyServiceRead(
                service_id=service.id,
                code=service.code,
                names=service.names,
                is_system=service.is_system,
                enabled=row is not None if configured else True,
                sla=sla,
                overrides={TicketPriority(k): SlaPair(**v) for k, v in property_overrides.items()},
            )
        )
    return PropertyServicesRead(configured=configured, services=result)


@router.get("/{property_id}/services", response_model=PropertyServicesRead)
def get_property_services(property_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _require_admin(user)
    item = _get_property(db, user, property_id)
    response = _read(db, item)
    db.commit()  # active_services may have just seeded the catalog
    return response


@router.put("/{property_id}/services", response_model=PropertyServicesRead)
def update_property_services(
    property_id: uuid.UUID, payload: PropertyServicesUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    _require_admin(user)
    item = _get_property(db, user, property_id)
    known = {s.id for s in active_services(db, item.organization_id)}
    seen: set[uuid.UUID] = set()
    for entry in payload.services:
        if entry.service_id not in known:
            raise HTTPException(400, f"Unknown service: {entry.service_id}")
        if entry.service_id in seen:
            raise HTTPException(400, f"Service listed twice: {entry.service_id}")
        seen.add(entry.service_id)

    db.execute(delete(PropertyService).where(PropertyService.property_id == item.id))
    for entry in payload.services:
        sla = {priority.value: pair.model_dump() for priority, pair in entry.sla.items()}
        db.add(PropertyService(organization_id=item.organization_id, property_id=item.id, service_id=entry.service_id, sla=sla or None))
    db.commit()
    return _read(db, item)
