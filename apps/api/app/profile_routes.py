from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from .auth import get_current_user
from .db import get_db
from .models import Channel, User
from .staff_link import issue_link_code, unlink
from .telegram_webhook import bot_username

router = APIRouter(prefix="/me", tags=["me"])


class TelegramStatus(BaseModel):
    linked: bool
    channel_available: bool


class TelegramLinkCode(BaseModel):
    code: str
    expires_at: datetime
    deep_link: str | None = None


def _telegram_channel(db: Session, user: User) -> Channel | None:
    """The organization's connected Telegram bot: the one staff link to and get notified through."""
    return db.scalar(
        select(Channel)
        .where(Channel.organization_id == user.organization_id, Channel.type == "telegram", Channel.status == "connected")
        .order_by(Channel.created_at.desc())
    )


def _usable(channel: Channel | None) -> bool:
    return channel is not None and bool((channel.credentials or {}).get("bot_token"))


@router.get("/telegram", response_model=TelegramStatus)
def telegram_status(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> TelegramStatus:
    return TelegramStatus(linked=user.telegram_linked, channel_available=_usable(_telegram_channel(db, user)))


@router.post("/telegram-link-code", response_model=TelegramLinkCode)
def create_telegram_link_code(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> TelegramLinkCode:
    channel = _telegram_channel(db, user)
    if not _usable(channel):
        raise HTTPException(409, "No Telegram bot is connected for this organization")
    code, expires_at = issue_link_code(db, user)
    username = bot_username(channel)
    return TelegramLinkCode(code=code, expires_at=expires_at, deep_link=f"https://t.me/{username}?start={code}" if username else None)


@router.delete("/telegram-link", status_code=204)
def delete_telegram_link(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Response:
    unlink(db, user)
    return Response(status_code=204)
