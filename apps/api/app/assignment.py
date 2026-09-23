import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import Ticket, TicketStatus, User, UserRole

ASSIGNABLE_ROLES = (UserRole.STAFF, UserRole.TECHNICIAN)


def find_assignee_for_category(db: Session, organization_id: uuid.UUID, category: str) -> User | None:
    """Pick the least-loaded staff/technician whose specialties include this ticket category.

    Load is measured by open (non-closed) tickets currently assigned to them, so requests
    fan out across matching staff instead of piling onto whoever matches first.
    """
    candidates = list(
        db.scalars(
            select(User).where(
                User.organization_id == organization_id,
                User.role.in_(ASSIGNABLE_ROLES),
                User.specialties.any(category),
            )
        ).all()
    )
    if not candidates:
        return None

    open_counts = dict(
        db.execute(
            select(Ticket.assignee_id, func.count(Ticket.id))
            .where(
                Ticket.organization_id == organization_id,
                Ticket.assignee_id.in_([c.id for c in candidates]),
                Ticket.status != TicketStatus.CLOSED,
            )
            .group_by(Ticket.assignee_id)
        ).all()
    )
    return min(candidates, key=lambda c: open_counts.get(c.id, 0))
