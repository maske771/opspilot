from datetime import datetime, timedelta, timezone

from .models import TicketPriority

SLA_MINUTES: dict[TicketPriority, tuple[int, int]] = {
    TicketPriority.CRITICAL: (15, 60),
    TicketPriority.HIGH: (30, 240),
    TicketPriority.MEDIUM: (120, 1440),
    TicketPriority.LOW: (480, 4320),
}


def calculate_sla(priority: TicketPriority, created_at: datetime | None = None, overrides: dict | None = None) -> tuple[datetime, datetime]:
    """overrides is Organization.sla_overrides: {"<priority value>": {"response_minutes": int, "resolution_minutes": int}},
    any key/field absent falls back to the SLA_MINUTES default for that priority."""
    created_at = created_at or datetime.now(timezone.utc)
    default_response, default_resolution = SLA_MINUTES[priority]
    override = (overrides or {}).get(priority.value) or {}
    response_minutes = override.get("response_minutes", default_response)
    resolution_minutes = override.get("resolution_minutes", default_resolution)
    return (
        created_at + timedelta(minutes=response_minutes),
        created_at + timedelta(minutes=resolution_minutes),
    )
