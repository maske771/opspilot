import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .auth import get_current_user, require_roles
from .db import get_db
from .models import Property, Unit, User

router = APIRouter(tags=["units"])


class UnitCreate(BaseModel):
    unit_number: str = Field(min_length=1, max_length=100)


class UnitUpdate(BaseModel):
    unit_number: str | None = Field(default=None, min_length=1, max_length=100)


class UnitRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    organization_id: uuid.UUID
    property_id: uuid.UUID
    unit_number: str


@router.get("/properties/{property_id}/units", response_model=list[UnitRead])
def list_property_units(
    property_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    property_item = db.get(Property, property_id)
    if property_item is None or property_item.organization_id != user.organization_id:
        raise HTTPException(404, "Property not found")
    stmt = select(Unit).where(
        Unit.organization_id == user.organization_id,
        Unit.property_id == property_id,
    ).order_by(Unit.unit_number)
    return list(db.scalars(stmt).all())


@router.post("/properties/{property_id}/units", response_model=UnitRead, status_code=201)
def create_property_unit(
    property_id: uuid.UUID,
    payload: UnitCreate,
    user: User = Depends(require_roles("owner", "admin", "manager")),
    db: Session = Depends(get_db),
):
    property_item = db.get(Property, property_id)
    if property_item is None or property_item.organization_id != user.organization_id:
        raise HTTPException(404, "Property not found")
    item = Unit(
        organization_id=user.organization_id,
        property_id=property_id,
        unit_number=payload.unit_number,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.patch("/units/{unit_id}", response_model=UnitRead)
def update_unit(
    unit_id: uuid.UUID,
    payload: UnitUpdate,
    user: User = Depends(require_roles("owner", "admin", "manager")),
    db: Session = Depends(get_db),
):
    item = db.get(Unit, unit_id)
    if item is None or item.organization_id != user.organization_id:
        raise HTTPException(404, "Unit not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/units/{unit_id}", status_code=204)
def delete_unit(
    unit_id: uuid.UUID,
    user: User = Depends(require_roles("owner", "admin")),
    db: Session = Depends(get_db),
):
    item = db.get(Unit, unit_id)
    if item is None or item.organization_id != user.organization_id:
        raise HTTPException(404, "Unit not found")
    db.delete(item)
    db.commit()
