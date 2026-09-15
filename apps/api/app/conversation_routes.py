import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from .auth import get_current_user
from .db import get_db
from .models import Conversation, Message, User

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


class MessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    conversation_id: uuid.UUID
    direction: str
    content: str
    external_message_id: str | None
    created_at: datetime


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
