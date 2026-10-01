import uuid
from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi import HTTPException

from app.analytics_routes import analytics_overview
from app.models import Organization, Property, Ticket, TicketPriority, TicketStatus, User, UserRole

BANGKOK_OFFSET = timedelta(hours=7)


def make_org(db_session, **overrides):
    org = Organization(name="Org", **overrides)
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


def test_only_managers_can_view_analytics(db_session):
    org = make_org(db_session)
    for role in (UserRole.STAFF, UserRole.TECHNICIAN):
        with pytest.raises(HTTPException) as exc:
            analytics_overview(period_from=None, period_to=None, user=make_user(db_session, org, role), db=db_session)
        assert exc.value.status_code == 403
    for role in (UserRole.OWNER, UserRole.ADMIN, UserRole.MANAGER):
        analytics_overview(period_from=None, period_to=None, user=make_user(db_session, org, role), db=db_session)  # must not raise


def test_default_range_is_the_last_30_days_in_the_orgs_timezone(db_session):
    org = make_org(db_session)
    owner = make_user(db_session, org, UserRole.OWNER)

    result = analytics_overview(period_from=None, period_to=None, user=owner, db=db_session)

    expected_end = datetime.now(timezone.utc).astimezone(timezone(BANGKOK_OFFSET)).date()
    assert result.period_end == expected_end
    assert (result.period_end - result.period_start).days == 29
    assert len(result.volume) == 30


def test_an_explicit_range_is_respected_and_fully_populated(db_session):
    org = make_org(db_session)
    owner = make_user(db_session, org, UserRole.OWNER)

    result = analytics_overview(period_from=date(2026, 6, 10), period_to=date(2026, 6, 12), user=owner, db=db_session)

    assert [v.date for v in result.volume] == [date(2026, 6, 10), date(2026, 6, 11), date(2026, 6, 12)]
    assert all(v.created == 0 and v.closed == 0 for v in result.volume)


def test_a_reversed_range_is_swapped_not_rejected(db_session):
    org = make_org(db_session)
    owner = make_user(db_session, org, UserRole.OWNER)

    result = analytics_overview(period_from=date(2026, 6, 12), period_to=date(2026, 6, 10), user=owner, db=db_session)

    assert result.period_start == date(2026, 6, 10)
    assert result.period_end == date(2026, 6, 12)


def test_volume_buckets_tickets_by_the_orgs_calendar_day(db_session):
    org = make_org(db_session)
    owner = make_user(db_session, org, UserRole.OWNER)
    # 2026-06-15 00:00 Bangkok (UTC+7) == 2026-06-14 17:00 UTC
    make_ticket(db_session, org, created_at=datetime(2026, 6, 14, 17, 0, tzinfo=timezone.utc))
    make_ticket(db_session, org, created_at=datetime(2026, 6, 15, 10, 0, tzinfo=timezone.utc))  # still 2026-06-15 Bangkok
    make_ticket(db_session, org, created_at=datetime(2026, 6, 14, 16, 59, tzinfo=timezone.utc))  # 2026-06-14 Bangkok, out of range
    make_ticket(db_session, org, status=TicketStatus.CLOSED, closed_at=datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc))

    result = analytics_overview(period_from=date(2026, 6, 15), period_to=date(2026, 6, 15), user=owner, db=db_session)

    assert len(result.volume) == 1
    assert result.volume[0].created == 2
    assert result.volume[0].closed == 1


def test_by_category_merges_created_and_closed_counts(db_session):
    org = make_org(db_session)
    owner = make_user(db_session, org, UserRole.OWNER)
    start = datetime(2026, 6, 14, 17, 0, tzinfo=timezone.utc)  # 2026-06-15 00:00 Bangkok

    make_ticket(db_session, org, category="plumbing", created_at=start + timedelta(hours=1))
    make_ticket(
        db_session,
        org,
        category="plumbing",
        status=TicketStatus.CLOSED,
        created_at=start + timedelta(hours=1),
        closed_at=start + timedelta(hours=3),
    )
    make_ticket(db_session, org, category="electrical", created_at=start + timedelta(hours=2))

    result = analytics_overview(period_from=date(2026, 6, 15), period_to=date(2026, 6, 15), user=owner, db=db_session)

    by_cat = {row.category: row for row in result.by_category}
    assert by_cat["plumbing"].created == 2
    assert by_cat["plumbing"].closed == 1
    assert by_cat["plumbing"].avg_resolution_minutes == 120.0
    assert by_cat["electrical"].created == 1
    assert by_cat["electrical"].closed == 0
    assert by_cat["electrical"].avg_resolution_minutes is None


def test_by_property_counts_tickets_created_in_range(db_session):
    org = make_org(db_session)
    owner = make_user(db_session, org, UserRole.OWNER)
    prop = Property(organization_id=org.id, name="Sunset Tower")
    db_session.add(prop)
    db_session.flush()
    start = datetime(2026, 6, 14, 17, 0, tzinfo=timezone.utc)

    make_ticket(db_session, org, property_id=prop.id, created_at=start + timedelta(hours=1))
    make_ticket(db_session, org, property_id=prop.id, created_at=start + timedelta(hours=2))
    make_ticket(db_session, org, created_at=start + timedelta(hours=3))  # no property

    result = analytics_overview(period_from=date(2026, 6, 15), period_to=date(2026, 6, 15), user=owner, db=db_session)

    assert len(result.by_property) == 1
    assert result.by_property[0].name == "Sunset Tower"
    assert result.by_property[0].created == 2


def test_by_staff_counts_tickets_closed_in_range(db_session):
    org = make_org(db_session)
    owner = make_user(db_session, org, UserRole.OWNER)
    tech = make_user(db_session, org, UserRole.TECHNICIAN)
    start = datetime(2026, 6, 14, 17, 0, tzinfo=timezone.utc)

    make_ticket(db_session, org, assignee_id=tech.id, status=TicketStatus.CLOSED, created_at=start, closed_at=start + timedelta(hours=4))
    make_ticket(db_session, org, assignee_id=tech.id, status=TicketStatus.CLOSED, created_at=start, closed_at=start + timedelta(hours=2))
    make_ticket(db_session, org, status=TicketStatus.CLOSED, created_at=start, closed_at=start + timedelta(hours=1))  # unassigned

    result = analytics_overview(period_from=date(2026, 6, 15), period_to=date(2026, 6, 15), user=owner, db=db_session)

    assert len(result.by_staff) == 1
    assert result.by_staff[0].email == tech.email
    assert result.by_staff[0].closed == 2
    assert result.by_staff[0].avg_resolution_minutes == 180.0


def test_resolution_sla_met_missed_and_pending(db_session):
    org = make_org(db_session)
    owner = make_user(db_session, org, UserRole.OWNER)
    now = datetime.now(timezone.utc)

    make_ticket(db_session, org, created_at=now, status=TicketStatus.CLOSED, closed_at=now + timedelta(hours=1), resolution_deadline=now + timedelta(hours=2))  # met
    make_ticket(db_session, org, created_at=now, status=TicketStatus.CLOSED, closed_at=now + timedelta(hours=3), resolution_deadline=now + timedelta(hours=2))  # missed
    make_ticket(db_session, org, created_at=now, status=TicketStatus.NEW, resolution_deadline=now - timedelta(hours=1))  # missed: overdue, still open
    make_ticket(db_session, org, created_at=now, status=TicketStatus.NEW, resolution_deadline=now + timedelta(hours=1))  # pending

    result = analytics_overview(period_from=None, period_to=None, user=owner, db=db_session)

    assert result.sla.resolution.met == 1
    assert result.sla.resolution.missed == 2
    assert result.sla.resolution.pending == 1
    assert result.sla.resolution.met_pct == pytest.approx(33.3, abs=0.1)


def test_response_sla_met_missed_and_pending(db_session):
    org = make_org(db_session)
    owner = make_user(db_session, org, UserRole.OWNER)
    now = datetime.now(timezone.utc)

    make_ticket(db_session, org, created_at=now, first_responded_at=now + timedelta(minutes=5), response_deadline=now + timedelta(minutes=30))  # met
    make_ticket(db_session, org, created_at=now, first_responded_at=now + timedelta(minutes=45), response_deadline=now + timedelta(minutes=30))  # missed
    make_ticket(db_session, org, created_at=now, response_deadline=now - timedelta(minutes=5))  # missed: never responded, overdue
    make_ticket(db_session, org, created_at=now, response_deadline=now + timedelta(minutes=30))  # pending

    result = analytics_overview(period_from=None, period_to=None, user=owner, db=db_session)

    assert result.sla.response.met == 1
    assert result.sla.response.missed == 2
    assert result.sla.response.pending == 1


def test_results_are_scoped_to_the_callers_organization(db_session):
    org = make_org(db_session)
    other_org = make_org(db_session)
    owner = make_user(db_session, org, UserRole.OWNER)
    start = datetime(2026, 6, 14, 17, 0, tzinfo=timezone.utc)
    make_ticket(db_session, other_org, category="plumbing", created_at=start + timedelta(hours=1))

    result = analytics_overview(period_from=date(2026, 6, 15), period_to=date(2026, 6, 15), user=owner, db=db_session)

    assert result.by_category == []
    assert result.volume[0].created == 0
