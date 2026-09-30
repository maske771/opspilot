import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from .auth import get_current_user, require_roles
from .db import get_db
from .models import Organization, User

router = APIRouter(prefix="/organization", tags=["organization"])


class OrganizationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    onboarding_completed: bool


class OrganizationUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    onboarding_completed: bool | None = None


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
    for field, value in changes.items():
        setattr(organization, field, value)
    db.commit()
    db.refresh(organization)
    return organization
