import re
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import Ticket, TicketStatus, User
from .notifications import normalize_language

CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O/1/I: codes get typed and read aloud
CODE_LENGTH = 8
CODE_TTL = timedelta(minutes=10)

# "/link CODE" typed by hand, or "/start CODE" from a t.me/<bot>?start=CODE deep link
LINK_COMMAND = re.compile(r"^/(?:link|start)(?:@\w+)?\s+([A-Za-z0-9]{6,16})$")


@dataclass(frozen=True)
class LinkCommand:
    chat_id: str
    code: str
    language: str


def issue_link_code(db: Session, user: User, now: datetime | None = None) -> tuple[str, datetime]:
    now = now or datetime.now(timezone.utc)
    while True:
        code = "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))
        if db.scalar(select(User.id).where(User.telegram_link_code == code)) is None:
            break
    user.telegram_link_code = code
    user.telegram_link_expires_at = now + CODE_TTL
    db.commit()
    return code, user.telegram_link_expires_at


def unlink(db: Session, user: User) -> None:
    user.telegram_chat_id = None
    user.telegram_channel_id = None
    user.telegram_link_code = None
    user.telegram_link_expires_at = None
    db.commit()


def parse_link_command(payload: dict) -> LinkCommand | None:
    message = payload.get("message") or {}
    chat = message.get("chat") or {}
    if chat.get("type") != "private" or chat.get("id") is None:
        return None
    match = LINK_COMMAND.match((message.get("text") or "").strip())
    if match is None:
        return None
    sender = message.get("from") or {}
    return LinkCommand(chat_id=str(chat["id"]), code=match.group(1).upper(), language=normalize_language(sender.get("language_code")))


def complete_link(db: Session, organization_id: uuid.UUID, channel_id: uuid.UUID, command: LinkCommand, now: datetime | None = None) -> User | None:
    """Bind the chat to the user who holds this code. Codes are single-use, expire, and only work in their own organization."""
    now = now or datetime.now(timezone.utc)
    user = db.scalar(
        select(User).where(
            User.organization_id == organization_id,
            User.telegram_link_code == command.code,
            User.telegram_link_expires_at > now,
        )
    )
    if user is None:
        return None
    user.telegram_chat_id = command.chat_id
    user.telegram_channel_id = channel_id
    user.notify_language = command.language
    user.telegram_link_code = None
    user.telegram_link_expires_at = None
    return user


def open_ticket_count(db: Session, user: User) -> int:
    return int(
        db.scalar(
            select(func.count(Ticket.id)).where(
                Ticket.assignee_id == user.id,
                Ticket.status.notin_([TicketStatus.CLOSED, TicketStatus.COMPLETED]),
            )
        )
        or 0
    )
