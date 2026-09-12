import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from .db import get_db
from .models import Ticket, TicketPriority, TicketStatus
from .sla import calculate_sla

router = APIRouter(prefix="/tickets", tags=["tickets"])


class TicketCreate(BaseModel):
    organization_id: uuid.UUID
    title: str = Field(min_length=1, max_length=255)
    description: str = Field(min_length=1)
    customer_id: uuid.UUID | None = None
    property_id: uuid.UUID | None = None
    unit_id: uuid.UUID | None = None
    category: str = "other"
    priority: TicketPriority = TicketPriority.MEDIUM


class TicketRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    customer_id: uuid.UUID | None
    property_id: uuid.UUID | None
    unit_id: uuid.UUID | None
    title: str
    description: str
    category: str
    priority: TicketPriority
    status: TicketStatus
    assignee_id: uuid.UUID | None
    response_deadline: datetime | None
    resolution_deadline: datetime | None
    created_at: datetime
    updated_at: datetime


@router.post("", response_model=TicketRead, status_code=status.HTTP_201_CREATED)
def create_ticket(payload: TicketCreate, db: Session = Depends(get_db)) -> Ticket:
    ticket = Ticket(
        organization_id=payload.organization_id,
        customer_id=payload.customer_id,
        property_id=payload.property_id,
        unit_id=payload.unit_id,
        title=payload.title,
        description=payload.description,
        category=payload.category,
        priority=payload.priority,
        status=TicketStatus.NEW,
    )
    db.add(ticket)
    db.flush()

    response_deadline, resolution_deadline = calculate_sla(ticket.priority, ticket.created_at)
    ticket.response_deadline = response_deadline
    ticket.resolution_deadline = resolution_deadline

    db.commit()
    db.refresh(ticket)
    return ticket


@router.get("/{ticket_id}", response_model=TicketRead)
def get_ticket(ticket_id: uuid.UUID, db: Session = Depends(get_db)) -> Ticket:
    ticket = db.get(Ticket, ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket
