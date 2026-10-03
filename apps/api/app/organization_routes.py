import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from .audit import change, record
from .auth import get_current_user, require_roles
from .db import get_db
from .models import Organization, TicketPriority, User
from .sla import SLA_MINUTES

router = APIRouter(prefix="/organization", tags=["organization"])


class OrganizationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    onboarding_completed: bool


class OrganizationUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    onboarding_completed: bool | None = None


class SlaPair(BaseModel):
    response_minutes: int = Field(ge=1, le=43200)
    resolution_minutes: int = Field(ge=1, le=43200)


class OrgSlaUpdate(BaseModel):
    critical: SlaPair | None = None
    high: SlaPair | None = None
    medium: SlaPair | None = None
    low: SlaPair | None = None


class EffectiveSla(BaseModel):
    priority: TicketPriority
    response_minutes: int
    resolution_minutes: int
    is_custom: bool


def _effective_sla(organization: Organization) -> list[EffectiveSla]:
    overrides = organization.sla_overrides or {}
    result = []
    for priority, (default_response, default_resolution) in SLA_MINUTES.items():
        override = overrides.get(priority.value)
        result.append(
            EffectiveSla(
                priority=priority,
                response_minutes=(override or {}).get("response_minutes", default_response),
                resolution_minutes=(override or {}).get("resolution_minutes", default_resolution),
                is_custom=override is not None,
            )
        )
    return result


@router.get("", response_model=OrganizationRead)
def get_organization(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    organization = db.get(Organization, user.organization_id)
    if organization is None:
        raise HTTPException(404, "Organization not found")
    return organization


@router.patch("", response_model=OrganizationRead)
def update_organization(
    payload: OrganizationUpdate,
    user: User = Depends(require_roles("owner", "admin")),
    db: Session = Depends(get_db),
):
    organization = db.get(Organization, user.organization_id)
    if organization is None:
        raise HTTPException(404, "Organization not found")
    changes = payload.model_dump(exclude_unset=True)
    if "name" in changes:
        changes["name"] = changes["name"].strip()
        if not changes["name"]:
            raise HTTPException(422, "Organization name cannot be empty")
    if "name" in changes and changes["name"] != organization.name:
        record(db, organization_id=organization.id, actor=user, entity_type="organization", entity_id=organization.id, action="renamed", details=change(organization.name, changes["name"]))
    for field, value in changes.items():
        setattr(organization, field, value)
    db.commit()
    db.refresh(organization)
    return organization


@router.get("/sla", response_model=list[EffectiveSla])
def get_organization_sla(user: User = Depends(require_roles("owner", "admin")), db: Session = Depends(get_db)):
    organization = db.get(Organization, user.organization_id)
    if organization is None:
        raise HTTPException(404, "Organization not found")
    return _effective_sla(organization)


@router.patch("/sla", response_model=list[EffectiveSla])
def update_organization_sla(
    payload: OrgSlaUpdate,
    user: User = Depends(require_roles("owner", "admin")),
    db: Session = Depends(get_db),
):
    organization = db.get(Organization, user.organization_id)
    if organization is None:
        raise HTTPException(404, "Organization not found")
    changes = payload.model_dump(exclude_unset=True)
    overrides = dict(organization.sla_overrides or {})
    for priority_value, value in changes.items():
        if value is None:
            overrides.pop(priority_value, None)
        else:
            overrides[priority_value] = value
    if (overrides or None) != organization.sla_overrides:
        record(db, organization_id=organization.id, actor=user, entity_type="organization", entity_id=organization.id, action="sla_changed", details=change(organization.sla_overrides, overrides or None))
    organization.sla_overrides = overrides or None
    db.commit()
    db.refresh(organization)
    return _effective_sla(organization)
