import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException

from app.models import Organization, Ticket, TicketPriority, TicketStatus, User, UserRole
from app.report_routes import REPORT_TZ, daily_report

ICT_MIDNIGHT_UTC = timedelta(hours=7)  # 00:00 ICT == 17:00 UTC the previous day


def make_org(db_session):
    org = Organization(name="Org")
    db_session.add(org)
    db_session.flush()
    return org


def make_user(db_session, org, role):
    user = User(organization_id=org.id, email=f"{role.value}-{uuid.uuid4().hex[:6]}@example.com", password_hash="h", role=role)
    db_session.add(user)
    db_session.commit()
    return user


def make_ticket(db_session, org, **overrides):
    values = dict(organization_id=org.id, title="t", description="x", priority=TicketPriority.MEDIUM, status=TicketStatus.NEW, category="other")
    values.update(overrides)
    ticket = Ticket(**values)
    db_session.add(ticket)
    db_session.commit()
    return ticket


def test_only_managers_can_view_the_report(db_session):
    org = make_org(db_session)
    for role in (UserRole.STAFF, UserRole.TECHNICIAN):
        with pytest.raises(HTTPException) as exc:
            daily_report(report_date=None, user=make_user(db_session, org, role), db=db_session)
        assert exc.value.status_code == 403
    for role in (UserRole.OWNER, UserRole.ADMIN, UserRole.MANAGER):
        daily_report(report_date=None, user=make_user(db_session, org, role), db=db_session)  # must not raise


def test_default_date_is_yesterday_in_indochina_time(db_session):
    org = make_org(db_session)
    owner = make_user(db_session, org, UserRole.OWNER)
    expected = (datetime.now(REPORT_TZ) - timedelta(days=1)).date()

    result = daily_report(report_date=None, user=owner, db=db_session)

    assert result.date == expected


def test_period_bounds_match_the_ict_calendar_day(db_session):
    org = make_org(db_session)
    owner = make_user(db_session, org, UserRole.OWNER)
    from datetime import date as date_type
    day = date_type(2026, 6, 15)

    result = daily_report(report_date=day, user=owner, db=db_session)

    assert result.period_start == datetime(2026, 6, 14, 17, 0, tzinfo=timezone.utc)  # 2026-06-15 00:00 ICT
    assert result.period_end == datetime(2026, 6, 15, 17, 0, tzinfo=timezone.utc)


def test_counts_only_tickets_created_inside_the_day(db_session):
    org = make_org(db_session)
    owner = make_user(db_session, org, UserRole.OWNER)
    period_start = datetime(2026, 6, 14, 17, 0, tzinfo=timezone.utc)

    make_ticket(db_session, org, created_at=period_start, priority=TicketPriority.HIGH, category="hvac")  # in (inclusive start)
    make_ticket(db_session, org, created_at=period_start + timedelta(hours=12), priority=TicketPriority.LOW, category="other")
    make_ticket(db_session, org, created_at=period_start - timedelta(seconds=1))  # just before, excluded
    make_ticket(db_session, org, created_at=period_start + timedelta(days=1))  # next day, excluded

    from datetime import date as date_type
    result = daily_report(report_date=date_type(2026, 6, 15), user=owner, db=db_session)

    assert result.tickets_created == 2
    counts = {row.priority: row.count for row in result.tickets_created_by_priority}
    assert counts[TicketPriority.HIGH] == 1 and counts[TicketPriority.LOW] == 1
    categories = {row.category: row.count for row in result.tickets_created_by_category}
    assert categories == {"hvac": 1, "other": 1}


def test_counts_only_tickets_closed_inside_the_day(db_session):
    org = make_org(db_session)
    owner = make_user(db_session, org, UserRole.OWNER)
    period_start = datetime(2026, 6, 14, 17, 0, tzinfo=timezone.utc)

    make_ticket(db_session, org, status=TicketStatus.CLOSED, closed_at=period_start + timedelta(hours=3))
    make_ticket(db_session, org, status=TicketStatus.CLOSED, closed_at=period_start - timedelta(minutes=1))  # day before
    make_ticket(db_session, org, status=TicketStatus.NEW, closed_at=None)

    from datetime import date as date_type
    result = daily_report(report_date=date_type(2026, 6, 15), user=owner, db=db_session)

    assert result.tickets_closed == 1


def test_current_snapshot_counts_are_not_scoped_to_the_report_day(db_session):
    org = make_org(db_session)
    owner = make_user(db_session, org, UserRole.OWNER)
    now = datetime.now(timezone.utc)

    make_ticket(db_session, org, status=TicketStatus.IN_PROGRESS, resolution_deadline=now - timedelta(hours=1))
    make_ticket(db_session, org, status=TicketStatus.WAITING_APPROVAL, priority=TicketPriority.CRITICAL)
    make_ticket(db_session, org, status=TicketStatus.CLOSED, closed_at=now)

    result = daily_report(report_date=None, user=owner, db=db_session)

    assert result.currently_open == 2  # in_progress + waiting_approval; closed excluded
    assert result.currently_overdue == 1
    assert result.currently_waiting_approval == 1


def test_open_critical_high_lists_only_open_high_priority_with_assignee_and_overdue_flag(db_session):
    org = make_org(db_session)
    owner = make_user(db_session, org, UserRole.OWNER)
    tech = make_user(db_session, org, UserRole.TECHNICIAN)
    now = datetime.now(timezone.utc)

    overdue_critical = make_ticket(db_session, org, priority=TicketPriority.CRITICAL, status=TicketStatus.IN_PROGRESS, assignee_id=tech.id, resolution_deadline=now - timedelta(hours=2))
    on_track_high = make_ticket(db_session, org, priority=TicketPriority.HIGH, status=TicketStatus.ASSIGNED, resolution_deadline=now + timedelta(hours=5))
    make_ticket(db_session, org, priority=TicketPriority.MEDIUM, status=TicketStatus.ASSIGNED)  # not high/critical
    make_ticket(db_session, org, priority=TicketPriority.CRITICAL, status=TicketStatus.CLOSED, closed_at=now)  # closed, excluded

    result = daily_report(report_date=None, user=owner, db=db_session)

    ids = {row.id: row for row in result.open_critical_high}
    assert set(ids) == {overdue_critical.id, on_track_high.id}
    assert ids[overdue_critical.id].overdue is True and ids[overdue_critical.id].assignee_email == tech.email
    assert ids[on_track_high.id].overdue is False and ids[on_track_high.id].assignee_email is None


def test_report_is_scoped_to_the_callers_organization(db_session):
    org = make_org(db_session)
    other_org = make_org(db_session)
    owner = make_user(db_session, org, UserRole.OWNER)
    make_ticket(db_session, other_org, priority=TicketPriority.CRITICAL, status=TicketStatus.NEW)

    result = daily_report(report_date=None, user=owner, db=db_session)

    assert result.currently_open == 0 and result.open_critical_high == []
