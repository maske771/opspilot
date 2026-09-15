import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .auth import get_current_user, require_roles
from .db import get_db
from .models import Customer, User

router = APIRouter(prefix="/customers", tags=["customers"])


class CustomerCreate(BaseModel):
    organization_id: uuid.UUID
    name: str = Field(min_length=1, max_length=255)
    phone: str | None = None
    email: str | None = None


class CustomerUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    phone: str | None = None
    email: str | None = None


class CustomerRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    phone: str | None
    email: str | None


@router.get("", response_model=list[CustomerRead])
def list_customers(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return list(db.scalars(select(Customer).where(Customer.organization_id == user.organization_id).order_by(Customer.name)).all())


@router.post("", response_model=CustomerRead, status_code=201)
def create_customer(payload: CustomerCreate, user: User = Depends(require_roles("owner", "admin", "manager", "staff")), db: Session = Depends(get_db)):
    if payload.organization_id != user.organization_id:
        raise HTTPException(403, "Organization scope violation")
    customer = Customer(
        organization_id=user.organization_id,
        name=payload.name,
        phone=payload.phone,
        email=payload.email,
    )
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return customer


@router.get("/{customer_id}", response_model=CustomerRead)
def get_customer(customer_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    customer = db.get(Customer, customer_id)
    if customer is None or customer.organization_id != user.organization_id:
        raise HTTPException(404, "Customer not found")
    return customer


@router.patch("/{customer_id}", response_model=CustomerRead)
def update_customer(customer_id: uuid.UUID, payload: CustomerUpdate, user: User = Depends(require_roles("owner", "admin", "manager", "staff")), db: Session = Depends(get_db)):
    customer = db.get(Customer, customer_id)
    if customer is None or customer.organization_id != user.organization_id:
        raise HTTPException(404, "Customer not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(customer, field, value)
    db.commit()
    db.refresh(customer)
    return customer
