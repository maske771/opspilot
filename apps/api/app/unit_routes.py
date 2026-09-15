import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .auth import get_current_user, require_roles
from .db import get_db
from .models import Property, Unit, User

router = APIRouter(prefix="/units", tags=["units"])


class UnitCreate(BaseModel):
    organization_id: uuid.UUID
    property_id: uuid.UUID
    name: str = Field(min_length=1, max_length=100)
    unit_type: str | None = None


class UnitUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    unit_type: str | None = None


class UnitRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    organization_id: uuid.UUID
    property_id: uuid.UUID
    name: str
    unit_type: str | None


@router.get("", response_model=list[UnitRead])
def list_units(property_id: uuid.UUID | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    stmt = select(Unit).where(Unit.organization_id == user.organization_id)
    if property_id is not None:
        stmt = stmt.where(Unit.property_id == property_id)
    return list(db.scalars(stmt.order_by(Unit.name)).all())


@router.post("", response_model=UnitRead, status_code=201)
def create_unit(payload: UnitCreate, user: User = Depends(require_roles("owner", "admin", "manager")), db: Session = Depends(get_db)):
    if payload.organization_id != user.organization_id:
        raise HTTPException(403, "Organization scope violation")
    property_item = db.get(Property, payload.property_id)
    if property_item is None or property_item.organization_id != user.organization_id:
        raise HTTPException(404, "Property not found")
    item = Unit(organization_id=user.organization_id, property_id=payload.property_id, name=payload.name, unit_type=payload.unit_type)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.get("/{unit_id}", response_model=UnitRead)
def get_unit(unit_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = db.get(Unit, unit_id)
    if item is None or item.organization_id != user.organization_id:
        raise HTTPException(404, "Unit not found")
    return item


@router.patch("/{unit_id}", response_model=UnitRead)
def update_unit(unit_id: uuid.UUID, payload: UnitUpdate, user: User = Depends(require_roles("owner", "admin", "manager")), db: Session = Depends(get_db)):
    item = db.get(Unit, unit_id)
    if item is None or item.organization_id != user.organization_id:
        raise HTTPException(404, "Unit not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/{unit_id}", status_code=204)
def delete_unit(unit_id: uuid.UUID, user: User = Depends(require_roles("owner", "admin")), db: Session = Depends(get_db)):
    item = db.get(Unit, unit_id)
    if item is None or item.organization_id != user.organization_id:
        raise HTTPException(404, "Unit not found")
    db.delete(item)
    db.commit()
