"""Audit trail: ticket history and sensitive admin actions.

`record` only adds the event to the session, so it is committed (or rolled back) together with
the change it describes. Details hold ids, codes and enum values — never secrets such as channel
credentials or webhook tokens.
"""
import enum
import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from .auth import get_current_user, require_roles
from .db import get_db
from .models import AuditEvent, Ticket, User

router = APIRouter(tags=["audit"])


def _plain(value: Any) -> Any:
    if isinstance(value, enum.Enum):
        return value.value
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, dict):
        return {k: _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_plain(v) for v in value]
    return value


def change(old: Any, new: Any) -> dict[str, Any]:
    return {"from": _plain(old), "to": _plain(new)}


def record(
    db: Session,
    *,
    organization_id: uuid.UUID,
    actor: User | None,
    entity_type: str,
    entity_id: uuid.UUID,
    action: str,
    details: dict[str, Any] | None = None,
) -> None:
    db.add(
        AuditEvent(
            organization_id=organization_id,
            actor_id=actor.id if actor is not None else None,
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            details=_plain(details or {}),
        )
    )


def record_ticket(db: Session, ticket: Ticket, actor: User | None, action: str, details: dict[str, Any] | None = None) -> None:
    record(db, organization_id=ticket.organization_id, actor=actor, entity_type="ticket", entity_id=ticket.id, action=action, details=details)


class AuditEventRead(BaseModel):
    id: uuid.UUID
    actor_id: uuid.UUID | None
    actor_email: str | None
    entity_type: str
    entity_id: uuid.UUID
    action: str
    details: dict[str, Any]
    created_at: datetime


def _read(db: Session, events: list[AuditEvent]) -> list[AuditEventRead]:
    actor_ids = {e.actor_id for e in events if e.actor_id is not None}
    emails = dict(db.execute(select(User.id, User.email).where(User.id.in_(actor_ids))).all()) if actor_ids else {}
    return [
        AuditEventRead(
            id=e.id,
            actor_id=e.actor_id,
            actor_email=emails.get(e.actor_id),
            entity_type=e.entity_type,
            entity_id=e.entity_id,
            action=e.action,
            details=e.details or {},
            created_at=e.created_at,
        )
        for e in events
    ]


@router.get("/tickets/{ticket_id}/history", response_model=list[AuditEventRead])
def ticket_history(ticket_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ticket = db.get(Ticket, ticket_id)
    if ticket is None or ticket.organization_id != user.organization_id:
        raise HTTPException(status_code=404, detail="Ticket not found")
    events = db.scalars(
        select(AuditEvent)
        .where(AuditEvent.organization_id == user.organization_id, AuditEvent.entity_type == "ticket", AuditEvent.entity_id == ticket_id)
        .order_by(AuditEvent.created_at)
    ).all()
    return _read(db, list(events))


@router.get("/audit-events", response_model=list[AuditEventRead])
def list_audit_events(
    entity_type: str | None = None,
    entity_id: uuid.UUID | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(require_roles("owner", "admin")),
    db: Session = Depends(get_db),
):
    stmt = select(AuditEvent).where(AuditEvent.organization_id == user.organization_id)
    if entity_type is not None:
        stmt = stmt.where(AuditEvent.entity_type == entity_type)
    if entity_id is not None:
        stmt = stmt.where(AuditEvent.entity_id == entity_id)
    events = db.scalars(stmt.order_by(AuditEvent.created_at.desc()).offset(offset).limit(limit)).all()
    return _read(db, list(events))
