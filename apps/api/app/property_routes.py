import uuid
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session
from .db import get_db
from .models import Property

router = APIRouter(prefix="/properties", tags=["properties"])

class PropertyCreate(BaseModel):
    organization_id: uuid.UUID
    name: str = Field(min_length=1, max_length=255)
    address: str | None = None

class PropertyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    address: str | None

@router.post("", response_model=PropertyRead, status_code=201)
def create_property(payload: PropertyCreate, db: Session = Depends(get_db)):
    item = Property(**payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item

@router.get("/{property_id}", response_model=PropertyRead)
def get_property(property_id: uuid.UUID, db: Session = Depends(get_db)):
    item = db.get(Property, property_id)
    if item is None:
        raise HTTPException(404, "Property not found")
    return item
