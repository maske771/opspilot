import uuid
from datetime import date as date_type, datetime, time, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from .auth import get_current_user
from .db import get_db
from .models import Organization, Property, Ticket, User
from .report_routes import org_timezone
from .roles import MANAGER_ROLES

router = APIRouter(prefix="/analytics", tags=["analytics"])

DEFAULT_RANGE_DAYS = 30
MAX_RANGE_DAYS = 365


class DayVolume(BaseModel):
    date: date_type
    created: int
    closed: int


class CategoryBreakdown(BaseModel):
    category: str
    created: int
    closed: int
    avg_resolution_minutes: float | None


class PropertyBreakdown(BaseModel):
    property_id: uuid.UUID
    name: str
    created: int


class StaffBreakdown(BaseModel):
    user_id: uuid.UUID
    email: str
    closed: int
    avg_resolution_minutes: float | None


class SlaBucket(BaseModel):
    met: int
    missed: int
    pending: int
    met_pct: float | None


class SlaSummary(BaseModel):
    response: SlaBucket
    resolution: SlaBucket


class AnalyticsOverview(BaseModel):
    period_start: date_type
    period_end: date_type
    volume: list[DayVolume]
    by_category: list[CategoryBreakdown]
    by_property: list[PropertyBreakdown]
    by_staff: list[StaffBreakdown]
    sla: SlaSummary


def _require_manager(user: User) -> None:
    if user.role not in MANAGER_ROLES:
        raise HTTPException(status_code=403, detail="Only owner, admin or manager can view analytics")


def _resolution_minutes_expr():
    return func.avg(func.extract("epoch", Ticket.closed_at - Ticket.created_at) / 60)


def _sla_bucket(db: Session, org_id: uuid.UUID, start: datetime, end: datetime, now: datetime, deadline_col, completed_col) -> SlaBucket:
    met = func.sum(case((completed_col.is_not(None) & (completed_col <= deadline_col), 1), else_=0))
    missed = func.sum(
        case(
            (completed_col.is_not(None) & (completed_col > deadline_col), 1),
            (completed_col.is_(None) & deadline_col.is_not(None) & (deadline_col < now), 1),
            else_=0,
        )
    )
    row = db.execute(
        select(met, missed).where(Ticket.organization_id == org_id, Ticket.created_at >= start, Ticket.created_at < end)
    ).one()
    met_count = int(row[0] or 0)
    missed_count = int(row[1] or 0)
    total = db.scalar(
        select(func.count(Ticket.id)).where(Ticket.organization_id == org_id, Ticket.created_at >= start, Ticket.created_at < end)
    ) or 0
    pending = total - met_count - missed_count
    decided = met_count + missed_count
    met_pct = round(100 * met_count / decided, 1) if decided else None
    return SlaBucket(met=met_count, missed=missed_count, pending=pending, met_pct=met_pct)


@router.get("/overview", response_model=AnalyticsOverview)
def analytics_overview(
    period_from: date_type | None = Query(default=None, alias="from"),
    period_to: date_type | None = Query(default=None, alias="to"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AnalyticsOverview:
    _require_manager(user)
    org = db.get(Organization, user.organization_id)
    tz = org_timezone(org)
    today = datetime.now(tz).date()
    period_to = period_to or today
    period_from = period_from or (period_to - timedelta(days=DEFAULT_RANGE_DAYS - 1))
    if period_to < period_from:
        period_from, period_to = period_to, period_from
    if (period_to - period_from).days > MAX_RANGE_DAYS:
        period_from = period_to - timedelta(days=MAX_RANGE_DAYS)

    start = datetime.combine(period_from, time.min, tzinfo=tz)
    end = datetime.combine(period_to, time.min, tzinfo=tz) + timedelta(days=1)
    now = datetime.now(timezone.utc)
    org_id = user.organization_id

    created_rows = db.scalars(
        select(Ticket.created_at).where(Ticket.organization_id == org_id, Ticket.created_at >= start, Ticket.created_at < end)
    ).all()
    closed_rows = db.scalars(
        select(Ticket.closed_at).where(Ticket.organization_id == org_id, Ticket.closed_at >= start, Ticket.closed_at < end)
    ).all()
    created_by_day: dict[date_type, int] = {}
    for ts in created_rows:
        d = ts.astimezone(tz).date()
        created_by_day[d] = created_by_day.get(d, 0) + 1
    closed_by_day: dict[date_type, int] = {}
    for ts in closed_rows:
        d = ts.astimezone(tz).date()
        closed_by_day[d] = closed_by_day.get(d, 0) + 1
    volume = []
    d = period_from
    while d <= period_to:
        volume.append(DayVolume(date=d, created=created_by_day.get(d, 0), closed=closed_by_day.get(d, 0)))
        d += timedelta(days=1)

    created_by_category = dict(
        db.execute(
            select(Ticket.category, func.count(Ticket.id))
            .where(Ticket.organization_id == org_id, Ticket.created_at >= start, Ticket.created_at < end)
            .group_by(Ticket.category)
        ).all()
    )
    closed_by_category = db.execute(
        select(Ticket.category, func.count(Ticket.id), _resolution_minutes_expr())
        .where(Ticket.organization_id == org_id, Ticket.closed_at >= start, Ticket.closed_at < end)
        .group_by(Ticket.category)
    ).all()
    closed_by_category_map = {row[0]: (row[1], row[2]) for row in closed_by_category}
    categories = set(created_by_category) | set(closed_by_category_map)
    by_category = [
        CategoryBreakdown(
            category=cat,
            created=created_by_category.get(cat, 0),
            closed=closed_by_category_map.get(cat, (0, None))[0],
            avg_resolution_minutes=round(closed_by_category_map[cat][1], 1) if closed_by_category_map.get(cat, (0, None))[1] is not None else None,
        )
        for cat in sorted(categories, key=lambda c: -created_by_category.get(c, 0))
    ]

    property_rows = db.execute(
        select(Ticket.property_id, func.count(Ticket.id))
        .where(Ticket.organization_id == org_id, Ticket.created_at >= start, Ticket.created_at < end, Ticket.property_id.is_not(None))
        .group_by(Ticket.property_id)
        .order_by(func.count(Ticket.id).desc())
    ).all()
    property_names = (
        {p.id: p.name for p in db.scalars(select(Property).where(Property.id.in_([r[0] for r in property_rows])))} if property_rows else {}
    )
    by_property = [
        PropertyBreakdown(property_id=pid, name=property_names.get(pid, "?"), created=count) for pid, count in property_rows
    ]

    staff_rows = db.execute(
        select(Ticket.assignee_id, func.count(Ticket.id), _resolution_minutes_expr())
        .where(
            Ticket.organization_id == org_id,
            Ticket.closed_at >= start,
            Ticket.closed_at < end,
            Ticket.assignee_id.is_not(None),
        )
        .group_by(Ticket.assignee_id)
        .order_by(func.count(Ticket.id).desc())
    ).all()
    staff_emails = (
        {u.id: u.email for u in db.scalars(select(User).where(User.id.in_([r[0] for r in staff_rows])))} if staff_rows else {}
    )
    by_staff = [
        StaffBreakdown(user_id=uid, email=staff_emails.get(uid, "?"), closed=count, avg_resolution_minutes=round(avg, 1) if avg is not None else None)
        for uid, count, avg in staff_rows
    ]

    sla = SlaSummary(
        response=_sla_bucket(db, org_id, start, end, now, Ticket.response_deadline, Ticket.first_responded_at),
        resolution=_sla_bucket(db, org_id, start, end, now, Ticket.resolution_deadline, Ticket.closed_at),
    )

    return AnalyticsOverview(
        period_start=period_from,
        period_end=period_to,
        volume=volume,
        by_category=by_category,
        by_property=by_property,
        by_staff=by_staff,
        sla=sla,
    )
