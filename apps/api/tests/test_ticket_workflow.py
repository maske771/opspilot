import uuid
from datetime import datetime, timezone

import pytest

from app.models import Organization, Ticket, TicketPriority, TicketStatus, User, UserRole
from app.sla import calculate_sla
from app.tickets import TicketCreate, _transition, create_ticket


def make_ticket(status: TicketStatus) -> Ticket:
    return Ticket(
        organization_id=uuid.uuid4(),
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


def test_sla_overrides_replace_both_minutes_for_the_matching_priority() -> None:
    created_at = datetime(2026, 9, 15, 10, 0, tzinfo=timezone.utc)
    response, resolution = calculate_sla(TicketPriority.HIGH, created_at, {"high": {"response_minutes": 10, "resolution_minutes": 90}})
    assert response.isoformat() == "2026-09-15T10:10:00+00:00"
    assert resolution.isoformat() == "2026-09-15T11:30:00+00:00"


def test_sla_override_can_set_only_one_of_the_two_minutes() -> None:
    created_at = datetime(2026, 9, 15, 10, 0, tzinfo=timezone.utc)
    response, resolution = calculate_sla(TicketPriority.HIGH, created_at, {"high": {"response_minutes": 5}})
    assert response.isoformat() == "2026-09-15T10:05:00+00:00"
    assert resolution.isoformat() == "2026-09-15T14:00:00+00:00"  # untouched default for HIGH


def test_sla_override_for_a_different_priority_does_not_apply() -> None:
    created_at = datetime(2026, 9, 15, 10, 0, tzinfo=timezone.utc)
    response, resolution = calculate_sla(TicketPriority.HIGH, created_at, {"critical": {"response_minutes": 1, "resolution_minutes": 1}})
    assert response.isoformat() == "2026-09-15T10:30:00+00:00"
    assert resolution.isoformat() == "2026-09-15T14:00:00+00:00"


def test_sla_overrides_none_and_empty_dict_both_mean_no_override() -> None:
    created_at = datetime(2026, 9, 15, 10, 0, tzinfo=timezone.utc)
    assert calculate_sla(TicketPriority.LOW, created_at, None) == calculate_sla(TicketPriority.LOW, created_at, {})


def test_creating_a_ticket_applies_the_organizations_sla_overrides(db_session):
    org = Organization(name="Org", sla_overrides={"critical": {"response_minutes": 2, "resolution_minutes": 10}})
    db_session.add(org)
    db_session.flush()
    owner = User(organization_id=org.id, email="owner@example.com", password_hash="h", role=UserRole.OWNER)
    db_session.add(owner)
    db_session.commit()

    ticket = create_ticket(
        TicketCreate(organization_id=org.id, title="Gas smell", description="x", priority=TicketPriority.CRITICAL),
        user=owner,
        db=db_session,
    )

    assert (ticket.response_deadline - ticket.created_at).total_seconds() == 2 * 60
    assert (ticket.resolution_deadline - ticket.created_at).total_seconds() == 10 * 60
