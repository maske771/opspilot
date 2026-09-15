import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .auth import get_current_user
from .db import get_db
from .models import Ticket, TicketPriority, TicketStatus, User
from .sla import calculate_sla

router = APIRouter(prefix="/tickets", tags=["tickets"])


class TicketCreate(BaseModel):
    organization_id: uuid.UUID
    title: str = Field(min_length=1, max_length=255)
    description: str = Field(min_length=1)
    customer_id: uuid.UUID | None = None
    property_id: uuid.UUID | None = None
    unit_id: uuid.UUID | None = None
    conversation_id: uuid.UUID | None = None
    category: str = "other"
    priority: TicketPriority = TicketPriority.MEDIUM


class TicketUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, min_length=1)
    category: str | None = Field(default=None, min_length=1, max_length=100)
    priority: TicketPriority | None = None
    assignee_id: uuid.UUID | None = None


class TicketAssign(BaseModel):
    assignee_id: uuid.UUID


class TicketRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    organization_id: uuid.UUID
    customer_id: uuid.UUID | None
    property_id: uuid.UUID | None
    unit_id: uuid.UUID | None
    conversation_id: uuid.UUID | None
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


def _get_ticket(ticket_id: uuid.UUID, user: User, db: Session) -> Ticket:
    ticket = db.get(Ticket, ticket_id)
    if ticket is None or ticket.organization_id != user.organization_id:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket


def _ensure_assignee(ticket: Ticket, assignee_id: uuid.UUID, db: Session) -> None:
    user = db.get(User, assignee_id)
    if user is None or user.organization_id != ticket.organization_id:
        raise HTTPException(status_code=400, detail="Assignee does not belong to ticket organization")


def _transition(ticket: Ticket, target: TicketStatus) -> None:
    allowed: dict[TicketStatus, set[TicketStatus]] = {
        TicketStatus.NEW: {TicketStatus.ASSIGNED, TicketStatus.IN_PROGRESS, TicketStatus.CLOSED},
        TicketStatus.ASSIGNED: {TicketStatus.ACCEPTED, TicketStatus.IN_PROGRESS, TicketStatus.CLOSED},
        TicketStatus.ACCEPTED: {TicketStatus.IN_PROGRESS, TicketStatus.WAITING_APPROVAL, TicketStatus.CLOSED},
        TicketStatus.IN_PROGRESS: {TicketStatus.COMPLETED, TicketStatus.WAITING_APPROVAL, TicketStatus.CLOSED},
        TicketStatus.COMPLETED: {TicketStatus.CLOSED},
        TicketStatus.WAITING_APPROVAL: {TicketStatus.IN_PROGRESS, TicketStatus.CLOSED},
        TicketStatus.CLOSED: set(),
    }
    if target not in allowed[ticket.status]:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Invalid ticket transition: {ticket.status.value} -> {target.value}")
    ticket.status = target


@router.get("", response_model=list[TicketRead])
def list_tickets(ticket_status: TicketStatus | None = Query(default=None, alias="status"), priority: TicketPriority | None = None, limit: int = Query(default=50, ge=1, le=100), offset: int = Query(default=0, ge=0), user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[Ticket]:
    stmt = select(Ticket).where(Ticket.organization_id == user.organization_id)
    if ticket_status is not None:
        stmt = stmt.where(Ticket.status == ticket_status)
    if priority is not None:
        stmt = stmt.where(Ticket.priority == priority)
    stmt = stmt.order_by(Ticket.created_at.desc()).offset(offset).limit(limit)
    return list(db.scalars(stmt).all())


@router.post("", response_model=TicketRead, status_code=status.HTTP_201_CREATED)
def create_ticket(payload: TicketCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Ticket:
    if payload.organization_id != user.organization_id:
        raise HTTPException(status_code=403, detail="Organization scope violation")
    if payload.conversation_id is not None:
        from .models import Conversation
        conversation = db.get(Conversation, payload.conversation_id)
        if conversation is None or conversation.organization_id != user.organization_id:
            raise HTTPException(status_code=400, detail="Conversation does not belong to organization")

    ticket = Ticket(organization_id=user.organization_id, customer_id=payload.customer_id, property_id=payload.property_id, unit_id=payload.unit_id, conversation_id=payload.conversation_id, title=payload.title, description=payload.description, category=payload.category, priority=payload.priority, status=TicketStatus.NEW)
    db.add(ticket)
    db.flush()
    ticket.response_deadline, ticket.resolution_deadline = calculate_sla(ticket.priority, ticket.created_at)
    db.commit()
    db.refresh(ticket)
    return ticket


@router.get("/{ticket_id}", response_model=TicketRead)
def get_ticket(ticket_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Ticket:
    return _get_ticket(ticket_id, user, db)


@router.patch("/{ticket_id}", response_model=TicketRead)
def update_ticket(ticket_id: uuid.UUID, payload: TicketUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Ticket:
    ticket = _get_ticket(ticket_id, user, db)
    changes = payload.model_dump(exclude_unset=True)
    if "assignee_id" in changes and changes["assignee_id"] is not None:
        _ensure_assignee(ticket, changes["assignee_id"], db)
    priority_changed = "priority" in changes and changes["priority"] != ticket.priority
    for field, value in changes.items():
        setattr(ticket, field, value)
    if priority_changed:
        ticket.response_deadline, ticket.resolution_deadline = calculate_sla(ticket.priority, ticket.created_at)
    if ticket.assignee_id is not None and ticket.status == TicketStatus.NEW:
        ticket.status = TicketStatus.ASSIGNED
    db.commit()
    db.refresh(ticket)
    return ticket


@router.post("/{ticket_id}/assign", response_model=TicketRead)
def assign_ticket(ticket_id: uuid.UUID, payload: TicketAssign, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Ticket:
    ticket = _get_ticket(ticket_id, user, db)
    _ensure_assignee(ticket, payload.assignee_id, db)
    ticket.assignee_id = payload.assignee_id
    if ticket.status == TicketStatus.NEW:
        ticket.status = TicketStatus.ASSIGNED
    db.commit()
    db.refresh(ticket)
    return ticket


def _apply_transition(ticket_id: uuid.UUID, target: TicketStatus, user: User, db: Session) -> Ticket:
    ticket = _get_ticket(ticket_id, user, db)
    _transition(ticket, target)
    db.commit()
    db.refresh(ticket)
    return ticket


@router.post("/{ticket_id}/accept", response_model=TicketRead)
def accept_ticket(ticket_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Ticket:
    return _apply_transition(ticket_id, TicketStatus.ACCEPTED, user, db)


@router.post("/{ticket_id}/start", response_model=TicketRead)
def start_ticket(ticket_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Ticket:
    return _apply_transition(ticket_id, TicketStatus.IN_PROGRESS, user, db)


@router.post("/{ticket_id}/complete", response_model=TicketRead)
def complete_ticket(ticket_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Ticket:
    return _apply_transition(ticket_id, TicketStatus.COMPLETED, user, db)


@router.post("/{ticket_id}/close", response_model=TicketRead)
def close_ticket(ticket_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Ticket:
    return _apply_transition(ticket_id, TicketStatus.CLOSED, user, db)
