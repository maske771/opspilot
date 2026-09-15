import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .auth import get_current_user, require_roles
from .db import get_db
from .models import Property, User

router = APIRouter(prefix="/properties", tags=["properties"])


class PropertyCreate(BaseModel):
    organization_id: uuid.UUID
    name: str = Field(min_length=1, max_length=255)
    address: str | None = None


class PropertyUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    address: str | None = None


class PropertyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    address: str | None


@router.get("", response_model=list[Property])
def list_properties(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return list(db.scalars(select(Property).where(Property.organization_id == user.organization_id).order_by(Property.name)).all())


@router.post("", response_model=PropertyRead, status_code=201)
def create_property(payload: PropertyCreate, user: User = Depends(require_roles("owner", "admin", "manager")), db: Session = Depends(get_db)):
    if payload.organization_id != user.organization_id:
        raise HTTPException(403, "Organization scope violation")
    item = Property(organization_id=user.organization_id, name=payload.name, address=payload.address)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.get("/{property_id}", response_model=PropertyRead)
def get_property(property_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = db.get(Property, property_id)
    if item is None or item.organization_id != user.organization_id:
        raise HTTPException(404, "Property not found")
    return item


@router.patch("/{property_id}", response_model=PropertyRead)
def update_property(property_id: uuid.UUID, payload: PropertyUpdate, user: User = Depends(require_roles("owner", "admin", "manager")), db: Session = Depends(get_db)):
    item = db.get(Property, property_id)
    if item is None or item.organization_id != user.organization_id:
        raise HTTPException(404, "Property not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/{property_id}", status_code=204)
def delete_property(property_id: uuid.UUID, user: User = Depends(require_roles("owner", "admin")), db: Session = Depends(get_db)):
    item = db.get(Property, property_id)
    if item is None or item.organization_id != user.organization_id:
        raise HTTPException(404, "Property not found")
    db.delete(item)
    db.commit()
