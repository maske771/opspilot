import re
import uuid
from datetime import date as date_type, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .auth import get_current_user
from .db import get_db
from .models import Organization, Ticket, TicketPriority, TicketStatus, User
from .roles import MANAGER_ROLES
from .tickets import OPEN_STATUSES

router = APIRouter(prefix="/reports", tags=["reports"])

DEFAULT_TIMEZONE = "Asia/Bangkok"

# A curated list, not the full IANA database (~400 zones) — keeps the settings dropdown short.
# The scheduler and report computation work with any valid IANA name; this list only bounds
# what organizations can pick through the API/UI.
ALLOWED_TIMEZONES = (
    "Asia/Bangkok",
    "Asia/Ho_Chi_Minh",
    "Asia/Singapore",
    "Asia/Jakarta",
    "Asia/Manila",
    "Asia/Hong_Kong",
    "Asia/Shanghai",
    "Asia/Tokyo",
    "Asia/Kolkata",
    "Asia/Dubai",
    "Europe/Moscow",
    "Europe/London",
    "Europe/Berlin",
    "UTC",
    "America/New_York",
    "America/Los_Angeles",
)

TIME_PATTERN = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")


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


class DailyReportSettings(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    daily_report_enabled: bool
    daily_report_time: str
    daily_report_timezone: str


class DailyReportSettingsUpdate(BaseModel):
    daily_report_enabled: bool | None = None
    daily_report_time: str | None = None
    daily_report_timezone: str | None = None

    @field_validator("daily_report_time")
    @classmethod
    def _valid_time(cls, value: str | None) -> str | None:
        if value is not None and not TIME_PATTERN.match(value):
            raise ValueError("time must be in HH:MM (24h) format")
        return value

    @field_validator("daily_report_timezone")
    @classmethod
    def _valid_timezone(cls, value: str | None) -> str | None:
        if value is not None and value not in ALLOWED_TIMEZONES:
            raise ValueError(f"timezone must be one of {', '.join(ALLOWED_TIMEZONES)}")
        return value


def _require_manager(user: User) -> None:
    if user.role not in MANAGER_ROLES:
        raise HTTPException(status_code=403, detail="Only owner, admin or manager can view the daily report")


def _require_admin(user: User) -> None:
    if user.role not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Only owner or admin can change daily report settings")


def org_timezone(org: Organization) -> ZoneInfo:
    try:
        return ZoneInfo(org.daily_report_timezone or DEFAULT_TIMEZONE)
    except ZoneInfoNotFoundError:
        return ZoneInfo(DEFAULT_TIMEZONE)


def compute_daily_report(db: Session, org_id: uuid.UUID, tz: ZoneInfo, report_date: date_type | None = None) -> DailyReport:
    report_date = report_date or (datetime.now(tz) - timedelta(days=1)).date()
    period_start = datetime.combine(report_date, time.min, tzinfo=tz)
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


@router.get("/daily", response_model=DailyReport)
def daily_report(
    report_date: date_type | None = Query(default=None, alias="date"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DailyReport:
    _require_manager(user)
    org = db.get(Organization, user.organization_id)
    return compute_daily_report(db, user.organization_id, org_timezone(org), report_date)


@router.get("/daily/settings", response_model=DailyReportSettings)
def get_daily_report_settings(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Organization:
    _require_admin(user)
    org = db.get(Organization, user.organization_id)
    if org is None:
        raise HTTPException(404, "Organization not found")
    return org


@router.patch("/daily/settings", response_model=DailyReportSettings)
def update_daily_report_settings(
    payload: DailyReportSettingsUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> Organization:
    _require_admin(user)
    org = db.get(Organization, user.organization_id)
    if org is None:
        raise HTTPException(404, "Organization not found")
    changes = payload.model_dump(exclude_unset=True, exclude_none=True)
    for field, value in changes.items():
        setattr(org, field, value)
    db.commit()
    db.refresh(org)
    return org
