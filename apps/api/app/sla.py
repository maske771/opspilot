from datetime import datetime, timedelta, timezone

from .models import TicketPriority

SLA_MINUTES: dict[TicketPriority, tuple[int, int]] = {
    TicketPriority.CRITICAL: (15, 60),
    TicketPriority.HIGH: (30, 240),
    TicketPriority.MEDIUM: (120, 1440),
    TicketPriority.LOW: (480, 4320),
}


def calculate_sla(priority: TicketPriority, created_at: datetime | None = None) -> tuple[datetime, datetime]:
    created_at = created_at or datetime.now(timezone.utc)
    response_minutes, resolution_minutes = SLA_MINUTES[priority]
    return (
        created_at + timedelta(minutes=response_minutes),
        created_at + timedelta(minutes=resolution_minutes),
    )
