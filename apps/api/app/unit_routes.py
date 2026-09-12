import uuid
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session
from .db import get_db
from .models import Property, Unit

router = APIRouter(prefix="/units", tags=["units"])

class UnitCreate(BaseModel):
    organization_id: uuid.UUID
    property_id: uuid.UUID
    name: str = Field(min_length=1, max_length=100)
    unit_type: str | None = None

class UnitRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    organization_id: uuid.UUID
    property_id: uuid.UUID
    name: str
    unit_type: str | None

@router.post("", response_model=UnitRead, status_code=201)
def create_unit(payload: UnitCreate, db: Session = Depends(get_db)):
    if db.get(Property, payload.property_id) is None:
        raise HTTPException(404, "Property not found")
    item = Unit(**payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item

@router.get("/{unit_id}", response_model=UnitRead)
def get_unit(unit_id: uuid.UUID, db: Session = Depends(get_db)):
    item = db.get(Unit, unit_id)
    if item is None:
        raise HTTPException(404, "Unit not found")
    return item
