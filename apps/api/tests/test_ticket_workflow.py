from datetime import datetime, timezone

import pytest

from app.models import Ticket, TicketPriority, TicketStatus
from app.sla import calculate_sla
from app.tickets import _transition


def make_ticket(status: TicketStatus) -> Ticket:
    return Ticket(
        organization_id=__import__("uuid").uuid4(),
        title="Test",
        description="Test ticket",
        status=status,
        priority=TicketPriority.MEDIUM,
    )


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (TicketStatus.NEW, TicketStatus.ASSIGNED),
        (TicketStatus.ASSIGNED, TicketStatus.ACCEPTED),
        (TicketStatus.ACCEPTED, TicketStatus.IN_PROGRESS),
        (TicketStatus.IN_PROGRESS, TicketStatus.COMPLETED),
        (TicketStatus.COMPLETED, TicketStatus.CLOSED),
        (TicketStatus.WAITING_APPROVAL, TicketStatus.IN_PROGRESS),
    ],
)
def test_valid_ticket_transitions(current: TicketStatus, target: TicketStatus) -> None:
    ticket = make_ticket(current)
    _transition(ticket, target)
    assert ticket.status == target


def test_invalid_ticket_transition() -> None:
    ticket = make_ticket(TicketStatus.CLOSED)
    with pytest.raises(Exception, match="Invalid ticket transition"):
        _transition(ticket, TicketStatus.IN_PROGRESS)


def test_sla_calculation() -> None:
    created_at = datetime(2026, 9, 15, 10, 0, tzinfo=timezone.utc)
    response, resolution = calculate_sla(TicketPriority.HIGH, created_at)
    assert response.isoformat() == "2026-09-15T10:30:00+00:00"
    assert resolution.isoformat() == "2026-09-15T14:00:00+00:00"
