import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .auth import get_current_user
from .db import get_db
from .models import Channel, Conversation, CustomerIdentity, Message, User
from .outbound import send_message

router = APIRouter(prefix="/conversations", tags=["conversations"])


class ConversationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    organization_id: uuid.UUID
    customer_id: uuid.UUID | None
    channel_id: uuid.UUID
    external_conversation_id: str | None
    status: str
    created_at: datetime
    updated_at: datetime


class AttachmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    content_type: str


class MessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    conversation_id: uuid.UUID
    direction: str
    content: str
    external_message_id: str | None
    created_at: datetime
    attachments: list[AttachmentRead] = []


@router.get("", response_model=list[ConversationRead])
def list_conversations(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return list(db.scalars(select(Conversation).where(Conversation.organization_id == user.organization_id).order_by(Conversation.updated_at.desc())).all())


@router.get("/{conversation_id}", response_model=ConversationRead)
def get_conversation(conversation_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    conversation = db.get(Conversation, conversation_id)
    if conversation is None or conversation.organization_id != user.organization_id:
        raise HTTPException(404, "Conversation not found")
    return conversation


@router.get("/{conversation_id}/messages", response_model=list[MessageRead])
def list_messages(conversation_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    conversation = db.get(Conversation, conversation_id)
    if conversation is None or conversation.organization_id != user.organization_id:
        raise HTTPException(404, "Conversation not found")
    return list(db.scalars(select(Message).where(Message.conversation_id == conversation_id).order_by(Message.created_at)).all())


class MessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=4000)


class MessageSendResult(BaseModel):
    message: MessageRead
    delivered: bool


@router.post("/{conversation_id}/messages", response_model=MessageSendResult, status_code=201)
def send_conversation_message(
    conversation_id: uuid.UUID,
    payload: MessageCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conversation = db.get(Conversation, conversation_id)
    if conversation is None or conversation.organization_id != user.organization_id:
        raise HTTPException(404, "Conversation not found")
    channel = db.get(Channel, conversation.channel_id)
    if channel is None:
        raise HTTPException(404, "Channel not found")
    if conversation.customer_id is None:
        raise HTTPException(400, "Conversation has no customer to reply to")
    identity = db.scalar(
        select(CustomerIdentity).where(
            CustomerIdentity.organization_id == user.organization_id,
            CustomerIdentity.customer_id == conversation.customer_id,
            CustomerIdentity.channel_type == channel.type,
        )
    )
    if identity is None:
        raise HTTPException(400, "No channel identity found for this customer")

    message = Message(conversation_id=conversation.id, direction="outbound", content=payload.content)
    db.add(message)
    db.commit()
    db.refresh(message)

    staff_name = user.email.split("@")[0].capitalize()
    signed_content = f"{staff_name}: {payload.content}"
    delivered = send_message(channel, identity.external_user_id, signed_content)
    return MessageSendResult(message=message, delivered=delivered)
