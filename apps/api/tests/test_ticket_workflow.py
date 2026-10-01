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


def test_closing_a_ticket_stamps_closed_at() -> None:
    ticket = make_ticket(TicketStatus.COMPLETED)
    assert ticket.closed_at is None
    before = datetime.now(timezone.utc)
    _transition(ticket, TicketStatus.CLOSED)
    assert ticket.closed_at is not None and ticket.closed_at >= before


def test_non_closing_transitions_leave_closed_at_alone() -> None:
    ticket = make_ticket(TicketStatus.NEW)
    _transition(ticket, TicketStatus.ASSIGNED)
    assert ticket.closed_at is None


def test_staying_within_new_or_assigned_does_not_stamp_first_responded_at() -> None:
    ticket = make_ticket(TicketStatus.NEW)
    _transition(ticket, TicketStatus.ASSIGNED)
    assert ticket.first_responded_at is None


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (TicketStatus.NEW, TicketStatus.IN_PROGRESS),
        (TicketStatus.NEW, TicketStatus.CLOSED),
        (TicketStatus.ASSIGNED, TicketStatus.ACCEPTED),
    ],
)
def test_leaving_new_or_assigned_stamps_first_responded_at(current: TicketStatus, target: TicketStatus) -> None:
    ticket = make_ticket(current)
    before = datetime.now(timezone.utc)
    _transition(ticket, target)
    assert ticket.first_responded_at is not None and ticket.first_responded_at >= before


def test_first_responded_at_is_stamped_only_once() -> None:
    ticket = make_ticket(TicketStatus.ASSIGNED)
    _transition(ticket, TicketStatus.ACCEPTED)
    first = ticket.first_responded_at
    _transition(ticket, TicketStatus.IN_PROGRESS)
    assert ticket.first_responded_at == first


def test_invalid_ticket_transition() -> None:
    ticket = make_ticket(TicketStatus.CLOSED)
    with pytest.raises(Exception, match="Invalid ticket transition"):
        _transition(ticket, TicketStatus.IN_PROGRESS)


def test_sla_calculation() -> None:
    created_at = datetime(2026, 9, 15, 10, 0, tzinfo=timezone.utc)
    response, resolution = calculate_sla(TicketPriority.HIGH, created_at)
    assert response.isoformat() == "2026-09-15T10:30:00+00:00"
    assert resolution.isoformat() == "2026-09-15T14:00:00+00:00"
