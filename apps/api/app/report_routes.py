import uuid
from datetime import date as date_type, datetime, time, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .auth import get_current_user
from .db import get_db
from .models import Ticket, TicketPriority, TicketStatus, User
from .roles import MANAGER_ROLES
from .tickets import OPEN_STATUSES

router = APIRouter(prefix="/reports", tags=["reports"])

# The MVP's initial ICP is Thailand-focused and organizations have no timezone setting yet,
# so "today"/"yesterday" for the report are fixed to Indochina Time (UTC+7, no DST).
REPORT_TZ = timezone(timedelta(hours=7))


class PriorityCount(BaseModel):
    priority: TicketPriority
    count: int


class CategoryCount(BaseModel):
    category: str
    count: int


class OpenTicketSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    title: str
    category: str
    priority: TicketPriority
    status: TicketStatus
    assignee_email: str | None
    created_at: datetime
    overdue: bool


class DailyReport(BaseModel):
    date: date_type
    period_start: datetime
    period_end: datetime
    tickets_created: int
    tickets_created_by_priority: list[PriorityCount]
    tickets_created_by_category: list[CategoryCount]
    tickets_closed: int
    currently_open: int
    currently_overdue: int
    currently_waiting_approval: int
    open_critical_high: list[OpenTicketSummary]


@router.get("/daily", response_model=DailyReport)
def daily_report(
    report_date: date_type | None = Query(default=None, alias="date"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DailyReport:
    if user.role not in MANAGER_ROLES:
        raise HTTPException(status_code=403, detail="Only owner, admin or manager can view the daily report")
    org_id = user.organization_id
    report_date = report_date or (datetime.now(REPORT_TZ) - timedelta(days=1)).date()
    period_start = datetime.combine(report_date, time.min, tzinfo=REPORT_TZ)
    period_end = period_start + timedelta(days=1)

    priority_rows = db.execute(
        select(Ticket.priority, func.count(Ticket.id))
        .where(Ticket.organization_id == org_id, Ticket.created_at >= period_start, Ticket.created_at < period_end)
        .group_by(Ticket.priority)
    ).all()
    category_rows = db.execute(
        select(Ticket.category, func.count(Ticket.id))
        .where(Ticket.organization_id == org_id, Ticket.created_at >= period_start, Ticket.created_at < period_end)
        .group_by(Ticket.category)
        .order_by(func.count(Ticket.id).desc())
    ).all()
    tickets_closed = db.scalar(
        select(func.count(Ticket.id)).where(
            Ticket.organization_id == org_id, Ticket.closed_at >= period_start, Ticket.closed_at < period_end
        )
    ) or 0

    now = datetime.now(timezone.utc)
    currently_open = db.scalar(
        select(func.count(Ticket.id)).where(Ticket.organization_id == org_id, Ticket.status.in_(OPEN_STATUSES))
    ) or 0
    currently_overdue = db.scalar(
        select(func.count(Ticket.id)).where(
            Ticket.organization_id == org_id,
            Ticket.status != TicketStatus.CLOSED,
            Ticket.resolution_deadline.is_not(None),
            Ticket.resolution_deadline < now,
        )
    ) or 0
    currently_waiting_approval = db.scalar(
        select(func.count(Ticket.id)).where(Ticket.organization_id == org_id, Ticket.status == TicketStatus.WAITING_APPROVAL)
    ) or 0

    open_high_priority = list(
        db.scalars(
            select(Ticket)
            .where(
                Ticket.organization_id == org_id,
                Ticket.status.in_(OPEN_STATUSES),
                Ticket.priority.in_((TicketPriority.HIGH, TicketPriority.CRITICAL)),
            )
            .order_by(Ticket.priority, Ticket.created_at)
        ).all()
    )
    assignee_ids = {t.assignee_id for t in open_high_priority if t.assignee_id}
    assignee_emails = {u.id: u.email for u in db.scalars(select(User).where(User.id.in_(assignee_ids)))} if assignee_ids else {}

    return DailyReport(
        date=report_date,
        period_start=period_start,
        period_end=period_end,
        tickets_created=sum(count for _, count in priority_rows),
        tickets_created_by_priority=[PriorityCount(priority=p, count=int(c)) for p, c in priority_rows],
        tickets_created_by_category=[CategoryCount(category=cat, count=int(c)) for cat, c in category_rows],
        tickets_closed=int(tickets_closed),
        currently_open=int(currently_open),
        currently_overdue=int(currently_overdue),
        currently_waiting_approval=int(currently_waiting_approval),
        open_critical_high=[
            OpenTicketSummary(
                id=t.id,
                title=t.title,
                category=t.category,
                priority=t.priority,
                status=t.status,
                assignee_email=assignee_emails.get(t.assignee_id),
                created_at=t.created_at,
                overdue=bool(t.resolution_deadline and t.resolution_deadline < now),
            )
            for t in open_high_priority
        ],
    )
