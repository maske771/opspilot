import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .auth import get_current_user, require_roles
from .db import get_db
from .models import Channel, User

router = APIRouter(prefix="/channels", tags=["channels"])


class ChannelRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    organization_id: uuid.UUID
    type: str
    name: str
    status: str
    created_at: datetime


class ChannelConnect(BaseModel):
    name: str = Field(min_length=1, max_length=255)


class ChannelUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)


@router.get("", response_model=list[ChannelRead])
def list_channels(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return list(db.scalars(select(Channel).where(Channel.organization_id == user.organization_id).order_by(Channel.created_at)).all())


@router.post("/{channel_type}/connect", response_model=ChannelRead, status_code=201)
def connect_channel(channel_type: str, payload: ChannelConnect, user: User = Depends(require_roles("owner", "admin")), db: Session = Depends(get_db)):
    channel_type = channel_type.strip().lower()
    if channel_type not in {"line", "whatsapp", "telegram", "email"}:
        raise HTTPException(400, "Unsupported channel type")
    channel = Channel(organization_id=user.organization_id, type=channel_type, name=payload.name.strip(), status="connected")
    db.add(channel)
    db.commit()
    db.refresh(channel)
    return channel


@router.post("/{channel_type}/disconnect", response_model=ChannelRead)
def disconnect_channel(channel_type: str, user: User = Depends(require_roles("owner", "admin")), db: Session = Depends(get_db)):
    channel = db.scalar(select(Channel).where(Channel.organization_id == user.organization_id, Channel.type == channel_type.lower(), Channel.status == "connected").order_by(Channel.created_at.desc()))
    if channel is None:
        raise HTTPException(404, "Connected channel not found")
    channel.status = "disconnected"
    db.commit()
    db.refresh(channel)
    return channel


@router.get("/{channel_id}", response_model=ChannelRead)
def get_channel(channel_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    channel = db.get(Channel, channel_id)
    if channel is None or channel.organization_id != user.organization_id:
        raise HTTPException(404, "Channel not found")
    return channel


@router.patch("/{channel_id}", response_model=ChannelRead)
def update_channel(channel_id: uuid.UUID, payload: ChannelUpdate, user: User = Depends(require_roles("owner", "admin")), db: Session = Depends(get_db)):
    channel = db.get(Channel, channel_id)
    if channel is None or channel.organization_id != user.organization_id:
        raise HTTPException(404, "Channel not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(channel, field, value.strip() if isinstance(value, str) else value)
    db.commit()
    db.refresh(channel)
    return channel


@router.post("/{channel_id}/test", response_model=ChannelRead)
def test_channel(channel_id: uuid.UUID, user: User = Depends(require_roles("owner", "admin")), db: Session = Depends(get_db)):
    channel = db.get(Channel, channel_id)
    if channel is None or channel.organization_id != user.organization_id:
        raise HTTPException(404, "Channel not found")
    return channel
