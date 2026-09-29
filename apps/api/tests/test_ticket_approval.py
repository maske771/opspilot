import uuid

import pytest
from fastapi import HTTPException

from app.models import Organization, Ticket, TicketPriority, TicketStatus, User, UserRole
from app.tickets import close_ticket, complete_ticket


def make_org_and_ticket(db_session, priority, status=TicketStatus.IN_PROGRESS):
    org = Organization(name="Org")
    db_session.add(org)
    db_session.flush()
    ticket = Ticket(organization_id=org.id, title="Leak", description="x", priority=priority, status=status)
    db_session.add(ticket)
    db_session.commit()
    return org, ticket


def make_user(db_session, org, role):
    user = User(organization_id=org.id, email=f"{role.value}-{uuid.uuid4().hex[:6]}@example.com", password_hash="h", role=role)
    db_session.add(user)
    db_session.commit()
    return user


@pytest.mark.parametrize("priority", [TicketPriority.HIGH, TicketPriority.CRITICAL])
def test_completing_a_high_or_critical_ticket_goes_to_waiting_approval(db_session, priority, monkeypatch):
    calls = []
    monkeypatch.setattr("app.tickets.notify_managers_approval_needed", lambda db, ticket: calls.append(ticket.id))
    org, ticket = make_org_and_ticket(db_session, priority)
    staff = make_user(db_session, org, UserRole.STAFF)

    result = complete_ticket(ticket.id, user=staff, db=db_session)

    assert result.status == TicketStatus.WAITING_APPROVAL
    assert calls == [ticket.id]


@pytest.mark.parametrize("priority", [TicketPriority.MEDIUM, TicketPriority.LOW])
def test_completing_a_medium_or_low_ticket_is_unchanged(db_session, priority, monkeypatch):
    calls = []
    monkeypatch.setattr("app.tickets.notify_managers_approval_needed", lambda db, ticket: calls.append(ticket.id))
    org, ticket = make_org_and_ticket(db_session, priority)
    staff = make_user(db_session, org, UserRole.STAFF)

    result = complete_ticket(ticket.id, user=staff, db=db_session)

    assert result.status == TicketStatus.COMPLETED
    assert calls == []


@pytest.mark.parametrize("role", [UserRole.STAFF, UserRole.TECHNICIAN])
def test_staff_cannot_close_a_high_or_critical_ticket(db_session, role, monkeypatch):
    monkeypatch.setattr("app.tickets.notify_managers_approval_needed", lambda db, ticket: None)
    org, ticket = make_org_and_ticket(db_session, TicketPriority.CRITICAL, status=TicketStatus.WAITING_APPROVAL)
    staff = make_user(db_session, org, role)

    with pytest.raises(HTTPException) as exc:
        close_ticket(ticket.id, user=staff, db=db_session)
    assert exc.value.status_code == 403
    db_session.refresh(ticket)
    assert ticket.status == TicketStatus.WAITING_APPROVAL


@pytest.mark.parametrize("role", [UserRole.OWNER, UserRole.ADMIN, UserRole.MANAGER])
def test_a_manager_can_close_a_high_or_critical_ticket(db_session, role, monkeypatch):
    monkeypatch.setattr("app.tickets.notify_managers_approval_needed", lambda db, ticket: None)
    org, ticket = make_org_and_ticket(db_session, TicketPriority.HIGH, status=TicketStatus.WAITING_APPROVAL)
    manager = make_user(db_session, org, role)

    result = close_ticket(ticket.id, user=manager, db=db_session)

    assert result.status == TicketStatus.CLOSED


def test_staff_can_still_close_a_medium_or_low_ticket(db_session):
    org, ticket = make_org_and_ticket(db_session, TicketPriority.LOW, status=TicketStatus.IN_PROGRESS)
    staff = make_user(db_session, org, UserRole.STAFF)

    result = close_ticket(ticket.id, user=staff, db=db_session)

    assert result.status == TicketStatus.CLOSED


def test_a_manager_can_close_a_high_ticket_directly_without_going_through_waiting_approval(db_session):
    # e.g. a duplicate/spam ticket — a manager's judgment call, not gated on the workflow state.
    org, ticket = make_org_and_ticket(db_session, TicketPriority.CRITICAL, status=TicketStatus.NEW)
    manager = make_user(db_session, org, UserRole.MANAGER)

    result = close_ticket(ticket.id, user=manager, db=db_session)

    assert result.status == TicketStatus.CLOSED
