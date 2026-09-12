import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from .db import get_db
from .models import Ticket, TicketStatus
from .ticket_service import TicketStateError, assign_ticket, transition_ticket

router = APIRouter(prefix="/tickets", tags=["tickets"])

@router.post("/{ticket_id}/assign")
def assign(ticket_id: uuid.UUID, assignee_id: uuid.UUID, db: Session = Depends(get_db)):
    ticket = db.get(Ticket, ticket_id)
    if ticket is None:
        raise HTTPException(404, "Ticket not found")
    try:
        assign_ticket(ticket, assignee_id)
    except TicketStateError as exc:
        raise HTTPException(409, str(exc)) from exc
    db.commit()
    db.refresh(ticket)
    return ticket

@router.post("/{ticket_id}/status/{new_status}")
def change_status(ticket_id: uuid.UUID, new_status: TicketStatus, db: Session = Depends(get_db)):
    ticket = db.get(Ticket, ticket_id)
    if ticket is None:
        raise HTTPException(404, "Ticket not found")
    try:
        transition_ticket(ticket, new_status)
    except TicketStateError as exc:
        raise HTTPException(409, str(exc)) from exc
    db.commit()
    db.refresh(ticket)
    return ticket
