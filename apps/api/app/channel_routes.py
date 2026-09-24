import uuid
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .auth import get_current_user, require_roles
from .db import get_db
from .models import Channel, User, UserRole, new_webhook_token
from .telegram_webhook import register_telegram_webhook, webhook_url

router = APIRouter(prefix="/channels", tags=["channels"])
SUPPORTED_CHANNELS = {"line", "whatsapp", "telegram", "email"}


class ChannelRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    organization_id: uuid.UUID
    type: str
    account_id: str
    name: str
    status: str
    has_credentials: bool
    webhook_token: str | None = None
    created_at: datetime


class ChannelConnect(BaseModel):
    account_id: str = Field(min_length=1, max_length=255)
    name: str = Field(min_length=1, max_length=255)
    credentials: dict[str, str] | None = None


class ChannelUpdate(BaseModel):
    account_id: str | None = Field(default=None, min_length=1, max_length=255)
    name: str | None = Field(default=None, min_length=1, max_length=255)
    credentials: dict[str, str] | None = None
    status: Literal["connected", "disconnected"] | None = None


def normalize_channel_value(value: str, label: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError(f"Channel {label} must not be blank")
    return value


def normalize_channel_name(name: str) -> str:
    return normalize_channel_value(name, "name")


def visible_channel(channel: Channel, user: User) -> ChannelRead:
    """The webhook token authenticates inbound traffic, so only owners and admins get to see it."""
    item = ChannelRead.model_validate(channel)
    if user.role not in (UserRole.OWNER, UserRole.ADMIN):
        item.webhook_token = None
    return item


@router.get("", response_model=list[ChannelRead])
def list_channels(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    channels = db.scalars(select(Channel).where(Channel.organization_id == user.organization_id).order_by(Channel.created_at)).all()
    return [visible_channel(channel, user) for channel in channels]


@router.post("/{channel_type}/connect", response_model=ChannelRead, status_code=201)
def connect_channel(channel_type: str, payload: ChannelConnect, user: User = Depends(require_roles("owner", "admin")), db: Session = Depends(get_db)):
    channel_type = channel_type.strip().lower()
    if channel_type not in SUPPORTED_CHANNELS:
        raise HTTPException(400, "Unsupported channel type")
    try:
        account_id = normalize_channel_value(payload.account_id, "account_id")
        name = normalize_channel_name(payload.name)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    channel = Channel(organization_id=user.organization_id, type=channel_type, account_id=account_id, name=name, status="connected", credentials=payload.credentials)
    db.add(channel)
    db.commit()
    db.refresh(channel)
    if channel.type == "telegram":
        register_telegram_webhook(channel)
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
    return visible_channel(channel, user)


@router.post("/{channel_id}/rotate-webhook-token", response_model=ChannelRead)
def rotate_webhook_token(channel_id: uuid.UUID, user: User = Depends(require_roles("owner", "admin")), db: Session = Depends(get_db)):
    """Issue a new webhook token; the old URL stops working at once. Telegram is re-pointed automatically."""
    channel = db.get(Channel, channel_id)
    if channel is None or channel.organization_id != user.organization_id:
        raise HTTPException(404, "Channel not found")
    channel.webhook_token = new_webhook_token()
    db.commit()
    db.refresh(channel)
    if channel.type == "telegram":
        register_telegram_webhook(channel)
    return channel


@router.post("/{channel_id}/register-webhook")
def register_webhook(channel_id: uuid.UUID, user: User = Depends(require_roles("owner", "admin")), db: Session = Depends(get_db)) -> dict[str, bool]:
    """Point the Telegram bot's webhook at this channel (also done automatically on connect, rotate and API start)."""
    channel = db.get(Channel, channel_id)
    if channel is None or channel.organization_id != user.organization_id:
        raise HTTPException(404, "Channel not found")
    if channel.type != "telegram":
        raise HTTPException(400, "Automatic webhook registration is only available for Telegram")
    if webhook_url(channel) is None:
        raise HTTPException(400, "PUBLIC_API_URL is not configured on the server")
    if not (channel.credentials or {}).get("bot_token"):
        raise HTTPException(400, "The channel has no bot token")
    if not register_telegram_webhook(channel):
        raise HTTPException(502, "Telegram did not accept the webhook")
    return {"registered": True}


@router.patch("/{channel_id}", response_model=ChannelRead)
def update_channel(channel_id: uuid.UUID, payload: ChannelUpdate, user: User = Depends(require_roles("owner", "admin")), db: Session = Depends(get_db)):
    channel = db.get(Channel, channel_id)
    if channel is None or channel.organization_id != user.organization_id:
        raise HTTPException(404, "Channel not found")
    changes = payload.model_dump(exclude_unset=True)
    try:
        for field, value in changes.items():
            if field != "credentials":
                if value is None:
                    continue
                value = normalize_channel_value(value, field)
            setattr(channel, field, value)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    db.commit()
    db.refresh(channel)
    if channel.type == "telegram" and channel.status == "connected" and ("credentials" in changes or "status" in changes):
        register_telegram_webhook(channel)
    return channel


@router.post("/{channel_id}/test", response_model=ChannelRead)
def test_channel(channel_id: uuid.UUID, user: User = Depends(require_roles("owner", "admin")), db: Session = Depends(get_db)):
    channel = db.get(Channel, channel_id)
    if channel is None or channel.organization_id != user.organization_id:
        raise HTTPException(404, "Channel not found")
    return channel
