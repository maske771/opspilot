import uuid
from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from .auth import get_current_user
from .db import get_db
from .models import Channel, Conversation, Customer, Message, Ticket, TicketPriority, TicketStatus, User

router = APIRouter(prefix="/inbox", tags=["inbox"])


class InboxCustomer(BaseModel):
    id: uuid.UUID
    name: str | None


class InboxChannel(BaseModel):
    id: uuid.UUID
    type: str
    name: str


class InboxLastMessage(BaseModel):
    content: str
    direction: str
    created_at: datetime


class InboxTicket(BaseModel):
    id: uuid.UUID
    status: TicketStatus
    priority: TicketPriority
    assignee_id: uuid.UUID | None


class InboxItem(BaseModel):
    conversation_id: uuid.UUID
    customer: InboxCustomer | None
    channel: InboxChannel
    last_message: InboxLastMessage | None
    ticket: InboxTicket | None
    updated_at: datetime


@router.get("", response_model=list[InboxItem])
def list_inbox(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[InboxItem]:
    conversations = db.scalars(
        select(Conversation)
        .where(Conversation.organization_id == user.organization_id)
        .order_by(Conversation.updated_at.desc())
        .limit(100)
    ).all()

    items: list[InboxItem] = []
    for conversation in conversations:
        customer = db.get(Customer, conversation.customer_id) if conversation.customer_id else None
        channel = db.get(Channel, conversation.channel_id)
        if channel is None:
            continue
        last_message = db.scalar(
            select(Message).where(Message.conversation_id == conversation.id).order_by(Message.created_at.desc())
        )
        ticket = db.scalar(
            select(Ticket)
            .where(Ticket.conversation_id == conversation.id, Ticket.status != TicketStatus.CLOSED)
            .order_by(Ticket.created_at.desc())
        )
        items.append(
            InboxItem(
                conversation_id=conversation.id,
                customer=InboxCustomer(id=customer.id, name=customer.name) if customer else None,
                channel=InboxChannel(id=channel.id, type=channel.type, name=channel.name),
                last_message=InboxLastMessage(
                    content=last_message.content, direction=last_message.direction, created_at=last_message.created_at
                )
                if last_message
                else None,
                ticket=InboxTicket(id=ticket.id, status=ticket.status, priority=ticket.priority, assignee_id=ticket.assignee_id)
                if ticket
                else None,
                updated_at=conversation.updated_at,
            )
        )
    return items
