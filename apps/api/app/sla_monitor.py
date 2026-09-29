import asyncio
import logging
import os
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .db import SessionLocal, engine
from .models import Ticket, TicketNotification, TicketStatus, User, UserRole
from .notifications import FAILED, SENT, send_to_user, ticket_message

logger = logging.getLogger("opspilot.sla")

LOCK_ID = 84210001  # Postgres advisory lock: only one API instance runs the monitor at a time
LOOKBACK = timedelta(days=7)
ASSIGNED_WINDOW = timedelta(hours=48)  # older tickets are not announced when the feature first turns on
STALE_AFTER = timedelta(hours=24)  # deadlines missed longer ago than this are history, not an alert
MAX_ATTEMPTS = 3

RESPONSE_OPEN = {TicketStatus.NEW, TicketStatus.ASSIGNED}
RESOLUTION_OPEN = {TicketStatus.NEW, TicketStatus.ASSIGNED, TicketStatus.ACCEPTED, TicketStatus.IN_PROGRESS}
MANAGER_ROLES = (UserRole.OWNER, UserRole.ADMIN, UserRole.MANAGER)

# (statuses the deadline applies to, deadline attribute, kinds, warn lead as a share of the window, minimum lead in minutes)
DEADLINES = (
    (RESPONSE_OPEN, "response_deadline", ("response_soon", "response_overdue", "escalation_response"), 0.2, 2),
    (RESOLUTION_OPEN, "resolution_deadline", ("resolution_soon", "resolution_overdue", "escalation_resolution"), 0.1, 5),
)


@dataclass(frozen=True)
class Notice:
    ticket: Ticket
    user: User
    kind: str
    minutes: int
    assignee: User | None


def _minutes(delta: timedelta) -> int:
    return max(1, round(delta.total_seconds() / 60))


def collect_notices(db: Session, now: datetime) -> list[Notice]:
    tickets = db.scalars(
        select(Ticket).where(Ticket.status.in_(RESOLUTION_OPEN), Ticket.created_at >= now - LOOKBACK)
    ).all()
    if not tickets:
        return []

    users = {u.id: u for u in db.scalars(select(User).where(User.organization_id.in_({t.organization_id for t in tickets})))}
    managers: dict = defaultdict(list)
    for user in users.values():
        if user.role in MANAGER_ROLES:
            managers[user.organization_id].append(user)

    notices: list[Notice] = []
    for ticket in tickets:
        assignee = users.get(ticket.assignee_id) if ticket.assignee_id else None

        if assignee is not None and ticket.created_at >= now - ASSIGNED_WINDOW:
            left = (ticket.response_deadline - now) if ticket.response_deadline else timedelta(hours=1)
            notices.append(Notice(ticket, assignee, "assigned", _minutes(left), assignee))

        for statuses, attribute, (soon, overdue, escalation), fraction, minimum in DEADLINES:
            deadline = getattr(ticket, attribute)
            if ticket.status not in statuses or deadline is None:
                continue
            remaining = deadline - now
            if remaining > timedelta(0):
                lead = max(timedelta(minutes=minimum), (deadline - ticket.created_at) * fraction)
                if assignee is not None and remaining <= lead:
                    notices.append(Notice(ticket, assignee, soon, _minutes(remaining), assignee))
            elif -remaining <= STALE_AFTER:
                late = _minutes(-remaining)
                if assignee is not None:
                    notices.append(Notice(ticket, assignee, overdue, late, assignee))
                for manager in managers[ticket.organization_id]:
                    if assignee is None or manager.id != assignee.id:
                        notices.append(Notice(ticket, manager, escalation, late, assignee))
    return notices


def dispatch(db: Session, notices: list[Notice]) -> int:
    """Send each notice at most once per (ticket, recipient, kind); failed sends are retried a few times."""
    if not notices:
        return 0
    existing = {
        (row.ticket_id, row.user_id, row.kind): row
        for row in db.scalars(select(TicketNotification).where(TicketNotification.ticket_id.in_({n.ticket.id for n in notices})))
    }
    sent = 0
    for notice in notices:
        row = existing.get((notice.ticket.id, notice.user.id, notice.kind))
        if row is not None and (row.status != FAILED or row.attempts >= MAX_ATTEMPTS):
            continue
        text = ticket_message(notice.kind, notice.ticket, notice.user.notify_language, notice.minutes, notice.assignee)
        result = send_to_user(db, notice.user, text)
        if row is None:
            db.add(TicketNotification(ticket_id=notice.ticket.id, user_id=notice.user.id, kind=notice.kind, status=result, attempts=1))
        else:
            row.status = result
            row.attempts += 1
        db.commit()  # after every send, so a crash can't make the previous ones go out again
        if result == SENT:
            sent += 1
    return sent


def run_tick(db: Session, now: datetime | None = None) -> int:
    now = now or datetime.now(timezone.utc)
    return dispatch(db, collect_notices(db, now))


def tick_once() -> int:
    with engine.connect() as lock_connection:
        if not lock_connection.execute(select(func.pg_try_advisory_lock(LOCK_ID))).scalar():
            return 0
        try:
            with SessionLocal() as db:
                return run_tick(db)
        finally:
            lock_connection.execute(select(func.pg_advisory_unlock(LOCK_ID)))
            lock_connection.commit()


def monitor_enabled() -> bool:
    return os.getenv("SLA_WORKER_ENABLED", "true").lower() not in ("0", "false", "no")


async def run_forever() -> None:
    interval = float(os.getenv("SLA_WORKER_INTERVAL_SECONDS", "30"))
    logger.info("SLA monitor started (every %ss)", interval)
    while True:
        try:
            sent = await asyncio.to_thread(tick_once)
            if sent:
                logger.info("SLA monitor sent %s notification(s)", sent)
        except Exception:
            logger.exception("SLA monitor tick failed")
        await asyncio.sleep(interval)
