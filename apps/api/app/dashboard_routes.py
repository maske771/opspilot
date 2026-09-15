from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .auth import get_current_user
from .db import get_db
from .models import Customer, Property, Ticket, TicketPriority, TicketStatus, Unit, User

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


class TicketStatusCount(BaseModel):
    status: TicketStatus
    count: int


class TicketPriorityCount(BaseModel):
    priority: TicketPriority
    count: int


class DashboardSummary(BaseModel):
    tickets_total: int
    tickets_open: int
    tickets_overdue: int
    customers_total: int
    properties_total: int
    units_total: int
    tickets_by_status: list[TicketStatusCount]
    tickets_by_priority: list[TicketPriorityCount]


@router.get("/summary", response_model=DashboardSummary)
def dashboard_summary(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DashboardSummary:
    org_id = user.organization_id
    open_statuses = {
        TicketStatus.NEW,
        TicketStatus.ASSIGNED,
        TicketStatus.ACCEPTED,
        TicketStatus.IN_PROGRESS,
        TicketStatus.WAITING_APPROVAL,
    }
    now = datetime.now(timezone.utc)

    tickets_total = db.scalar(
        select(func.count(Ticket.id)).where(Ticket.organization_id == org_id)
    ) or 0
    tickets_open = db.scalar(
        select(func.count(Ticket.id)).where(
            Ticket.organization_id == org_id,
            Ticket.status.in_(open_statuses),
        )
    ) or 0
    tickets_overdue = db.scalar(
        select(func.count(Ticket.id)).where(
            Ticket.organization_id == org_id,
            Ticket.status != TicketStatus.CLOSED,
            Ticket.resolution_deadline.is_not(None),
            Ticket.resolution_deadline < now,
        )
    ) or 0

    customers_total = db.scalar(
        select(func.count(Customer.id)).where(Customer.organization_id == org_id)
    ) or 0
    properties_total = db.scalar(
        select(func.count(Property.id)).where(Property.organization_id == org_id)
    ) or 0
    units_total = db.scalar(
        select(func.count(Unit.id)).where(Unit.organization_id == org_id)
    ) or 0

    status_rows = db.execute(
        select(Ticket.status, func.count(Ticket.id))
        .where(Ticket.organization_id == org_id)
        .group_by(Ticket.status)
    ).all()
    priority_rows = db.execute(
        select(Ticket.priority, func.count(Ticket.id))
        .where(Ticket.organization_id == org_id)
        .group_by(Ticket.priority)
    ).all()

    status_counts = {status: int(count) for status, count in status_rows}
    priority_counts = {priority: int(count) for priority, count in priority_rows}

    return DashboardSummary(
        tickets_total=int(tickets_total),
        tickets_open=int(tickets_open),
        tickets_overdue=int(tickets_overdue),
        customers_total=int(customers_total),
        properties_total=int(properties_total),
        units_total=int(units_total),
        tickets_by_status=[
            TicketStatusCount(status=status, count=status_counts.get(status, 0))
            for status in TicketStatus
        ],
        tickets_by_priority=[
            TicketPriorityCount(priority=priority, count=priority_counts.get(priority, 0))
            for priority in TicketPriority
        ],
    )
