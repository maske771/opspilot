import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .audit import change, record
from .auth import get_current_user, require_roles
from .db import get_db
from .models import Customer, Property, Unit, User, UserRole

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
    property_id: uuid.UUID | None = None
    unit_id: uuid.UUID | None = None


class CustomerRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    organization_id: uuid.UUID
    name: str | None
    phone: str | None
    email: str | None
    property_id: uuid.UUID | None
    unit_id: uuid.UUID | None


LINK_ROLES = (UserRole.OWNER, UserRole.ADMIN, UserRole.MANAGER)


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
    changes = payload.model_dump(exclude_unset=True)
    if "property_id" in changes or "unit_id" in changes:
        # The bot links a customer once on first contact; after that only managers change it.
        if user.role not in LINK_ROLES:
            raise HTTPException(403, "Only owner, admin or manager can change a customer's property")
        property_id = changes.get("property_id", customer.property_id)
        unit_id = changes.get("unit_id", customer.unit_id if "property_id" not in changes else None)
        if property_id is not None:
            prop = db.get(Property, property_id)
            if prop is None or prop.organization_id != user.organization_id:
                raise HTTPException(400, "Property not found")
        if unit_id is not None:
            unit = db.get(Unit, unit_id)
            if unit is None or unit.organization_id != user.organization_id or unit.property_id != property_id:
                raise HTTPException(400, "Unit does not belong to the property")
        changes["property_id"], changes["unit_id"] = property_id, unit_id
        if (property_id, unit_id) != (customer.property_id, customer.unit_id):
            record(
                db,
                organization_id=customer.organization_id,
                actor=user,
                entity_type="customer",
                entity_id=customer.id,
                action="property_changed",
                details={"name": customer.name, "property_id": change(customer.property_id, property_id), "unit_id": change(customer.unit_id, unit_id)},
            )
    for field, value in changes.items():
        setattr(customer, field, value)
    db.commit()
    db.refresh(customer)
    return customer
