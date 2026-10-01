import uuid
from datetime import date as date_type, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest
from fastapi import HTTPException

from app.models import Organization, Ticket, TicketPriority, TicketStatus, User, UserRole
from app.report_routes import (
    DailyReportSettingsUpdate,
    daily_report,
    get_daily_report_settings,
    org_timezone,
    update_daily_report_settings,
)

BANGKOK = ZoneInfo("Asia/Bangkok")


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


# ---- viewing the report

def test_only_managers_can_view_the_report(db_session):
    org = make_org(db_session)
    for role in (UserRole.STAFF, UserRole.TECHNICIAN):
        with pytest.raises(HTTPException) as exc:
            daily_report(report_date=None, user=make_user(db_session, org, role), db=db_session)
        assert exc.value.status_code == 403
    for role in (UserRole.OWNER, UserRole.ADMIN, UserRole.MANAGER):
        daily_report(report_date=None, user=make_user(db_session, org, role), db=db_session)  # must not raise


def test_organizations_default_to_bangkok_time(db_session):
    org = make_org(db_session)
    assert org.daily_report_timezone == "Asia/Bangkok"
    assert org_timezone(org) == BANGKOK


def test_default_date_is_yesterday_in_the_orgs_timezone(db_session):
    org = make_org(db_session)
    owner = make_user(db_session, org, UserRole.OWNER)
    expected = (datetime.now(BANGKOK) - timedelta(days=1)).date()

    result = daily_report(report_date=None, user=owner, db=db_session)

    assert result.date == expected


def test_period_bounds_match_the_orgs_calendar_day(db_session):
    org = make_org(db_session)
    owner = make_user(db_session, org, UserRole.OWNER)

    result = daily_report(report_date=date_type(2026, 6, 15), user=owner, db=db_session)

    assert result.period_start == datetime(2026, 6, 14, 17, 0, tzinfo=timezone.utc)  # 2026-06-15 00:00 Bangkok
    assert result.period_end == datetime(2026, 6, 15, 17, 0, tzinfo=timezone.utc)


def test_a_moscow_org_gets_moscow_day_bounds(db_session):
    org = make_org(db_session)
    org.daily_report_timezone = "Europe/Moscow"
    db_session.commit()
    owner = make_user(db_session, org, UserRole.OWNER)

    result = daily_report(report_date=date_type(2026, 6, 15), user=owner, db=db_session)

    assert result.period_start == datetime(2026, 6, 14, 21, 0, tzinfo=timezone.utc)  # 2026-06-15 00:00 MSK (UTC+3)


def test_counts_only_tickets_created_inside_the_day(db_session):
    org = make_org(db_session)
    owner = make_user(db_session, org, UserRole.OWNER)
    period_start = datetime(2026, 6, 14, 17, 0, tzinfo=timezone.utc)

    make_ticket(db_session, org, created_at=period_start, priority=TicketPriority.HIGH, category="hvac")
    make_ticket(db_session, org, created_at=period_start + timedelta(hours=12), priority=TicketPriority.LOW, category="other")
    make_ticket(db_session, org, created_at=period_start - timedelta(seconds=1))
    make_ticket(db_session, org, created_at=period_start + timedelta(days=1))

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
    make_ticket(db_session, org, status=TicketStatus.CLOSED, closed_at=period_start - timedelta(minutes=1))
    make_ticket(db_session, org, status=TicketStatus.NEW, closed_at=None)

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

    assert result.currently_open == 2
    assert result.currently_overdue == 1
    assert result.currently_waiting_approval == 1


def test_open_critical_high_lists_only_open_high_priority_with_assignee_and_overdue_flag(db_session):
    org = make_org(db_session)
    owner = make_user(db_session, org, UserRole.OWNER)
    tech = make_user(db_session, org, UserRole.TECHNICIAN)
    now = datetime.now(timezone.utc)

    overdue_critical = make_ticket(db_session, org, priority=TicketPriority.CRITICAL, status=TicketStatus.IN_PROGRESS, assignee_id=tech.id, resolution_deadline=now - timedelta(hours=2))
    on_track_high = make_ticket(db_session, org, priority=TicketPriority.HIGH, status=TicketStatus.ASSIGNED, resolution_deadline=now + timedelta(hours=5))
    make_ticket(db_session, org, priority=TicketPriority.MEDIUM, status=TicketStatus.ASSIGNED)
    make_ticket(db_session, org, priority=TicketPriority.CRITICAL, status=TicketStatus.CLOSED, closed_at=now)

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


# ---- delivery settings

def test_settings_default_to_disabled_with_sensible_defaults(db_session):
    org = make_org(db_session)
    owner = make_user(db_session, org, UserRole.OWNER)

    result = get_daily_report_settings(user=owner, db=db_session)

    assert result.daily_report_enabled is False
    assert result.daily_report_time == "08:00"
    assert result.daily_report_timezone == "Asia/Bangkok"


def test_only_owner_and_admin_can_read_or_change_settings(db_session):
    org = make_org(db_session)
    for role in (UserRole.MANAGER, UserRole.STAFF, UserRole.TECHNICIAN):
        user = make_user(db_session, org, role)
        with pytest.raises(HTTPException) as exc:
            get_daily_report_settings(user=user, db=db_session)
        assert exc.value.status_code == 403
        with pytest.raises(HTTPException):
            update_daily_report_settings(DailyReportSettingsUpdate(daily_report_enabled=True), user=user, db=db_session)


def test_updating_settings_persists_the_change(db_session):
    org = make_org(db_session)
    owner = make_user(db_session, org, UserRole.OWNER)

    result = update_daily_report_settings(
        DailyReportSettingsUpdate(daily_report_enabled=True, daily_report_time="09:30", daily_report_timezone="Europe/Moscow"),
        user=owner,
        db=db_session,
    )

    assert (result.daily_report_enabled, result.daily_report_time, result.daily_report_timezone) == (True, "09:30", "Europe/Moscow")
    db_session.refresh(org)
    assert org.daily_report_enabled is True and org.daily_report_time == "09:30"


def test_partial_update_only_touches_the_given_fields(db_session):
    org = make_org(db_session)
    owner = make_user(db_session, org, UserRole.OWNER)
    update_daily_report_settings(DailyReportSettingsUpdate(daily_report_enabled=True, daily_report_time="07:00"), user=owner, db=db_session)

    result = update_daily_report_settings(DailyReportSettingsUpdate(daily_report_time="10:15"), user=owner, db=db_session)

    assert result.daily_report_enabled is True  # untouched
    assert result.daily_report_time == "10:15"


@pytest.mark.parametrize("bad_time", ["9:00", "24:00", "12:60", "noon", ""])
def test_invalid_time_format_is_rejected(bad_time):
    with pytest.raises(Exception):
        DailyReportSettingsUpdate(daily_report_time=bad_time)


def test_unknown_timezone_is_rejected():
    with pytest.raises(Exception):
        DailyReportSettingsUpdate(daily_report_timezone="Mars/OlympusMons")


def test_settings_default_to_no_weekend_skip_no_excluded_dates_and_builtin_templates(db_session):
    org = make_org(db_session)
    owner = make_user(db_session, org, UserRole.OWNER)

    result = get_daily_report_settings(user=owner, db=db_session)

    assert result.daily_report_skip_weekends is False
    assert result.daily_report_excluded_dates == []
    assert set(result.daily_report_template) == {"en", "ru", "th"}
    assert all(v is False for v in result.daily_report_template_custom.values())
    assert "{date}" in result.daily_report_template["en"]


def test_skip_weekends_can_be_toggled(db_session):
    org = make_org(db_session)
    owner = make_user(db_session, org, UserRole.OWNER)

    result = update_daily_report_settings(DailyReportSettingsUpdate(daily_report_skip_weekends=True), user=owner, db=db_session)

    assert result.daily_report_skip_weekends is True


def test_excluded_dates_round_trip_sorted(db_session):
    org = make_org(db_session)
    owner = make_user(db_session, org, UserRole.OWNER)

    result = update_daily_report_settings(
        DailyReportSettingsUpdate(daily_report_excluded_dates=[date_type(2026, 12, 31), date_type(2026, 1, 1)]),
        user=owner,
        db=db_session,
    )

    assert result.daily_report_excluded_dates == [date_type(2026, 1, 1), date_type(2026, 12, 31)]


def test_excluded_dates_can_be_cleared_with_an_empty_list(db_session):
    org = make_org(db_session)
    owner = make_user(db_session, org, UserRole.OWNER)
    update_daily_report_settings(DailyReportSettingsUpdate(daily_report_excluded_dates=[date_type(2026, 1, 1)]), user=owner, db=db_session)

    result = update_daily_report_settings(DailyReportSettingsUpdate(daily_report_excluded_dates=[]), user=owner, db=db_session)

    assert result.daily_report_excluded_dates == []


def test_setting_a_custom_template_marks_only_that_language_custom(db_session):
    org = make_org(db_session)
    owner = make_user(db_session, org, UserRole.OWNER)

    result = update_daily_report_settings(
        DailyReportSettingsUpdate(daily_report_template={"en": "Today: {created} new, {closed} closed. {url}"}),
        user=owner,
        db=db_session,
    )

    assert result.daily_report_template["en"] == "Today: {created} new, {closed} closed. {url}"
    assert result.daily_report_template_custom["en"] is True
    assert result.daily_report_template_custom["ru"] is False
    assert result.daily_report_template_custom["th"] is False


def test_custom_template_persists_and_is_returned_by_a_later_get(db_session):
    org = make_org(db_session)
    owner = make_user(db_session, org, UserRole.OWNER)
    update_daily_report_settings(DailyReportSettingsUpdate(daily_report_template={"ru": "Сводка: {created}/{closed}"}), user=owner, db=db_session)

    result = get_daily_report_settings(user=owner, db=db_session)

    assert result.daily_report_template["ru"] == "Сводка: {created}/{closed}"
    assert result.daily_report_template_custom["ru"] is True


def test_setting_a_language_to_null_resets_it_to_the_builtin_template(db_session):
    org = make_org(db_session)
    owner = make_user(db_session, org, UserRole.OWNER)
    update_daily_report_settings(DailyReportSettingsUpdate(daily_report_template={"en": "Custom: {created}"}), user=owner, db=db_session)

    result = update_daily_report_settings(DailyReportSettingsUpdate(daily_report_template={"en": None}), user=owner, db=db_session)

    assert result.daily_report_template_custom["en"] is False
    assert "{date}" in result.daily_report_template["en"]


def test_updating_one_languages_template_leaves_other_overrides_alone(db_session):
    org = make_org(db_session)
    owner = make_user(db_session, org, UserRole.OWNER)
    update_daily_report_settings(DailyReportSettingsUpdate(daily_report_template={"en": "EN: {created}"}), user=owner, db=db_session)

    result = update_daily_report_settings(DailyReportSettingsUpdate(daily_report_template={"th": "TH: {created}"}), user=owner, db=db_session)

    assert result.daily_report_template_custom["en"] is True
    assert result.daily_report_template_custom["th"] is True
    assert result.daily_report_template["en"] == "EN: {created}"


@pytest.mark.parametrize(
    "bad_template",
    [
        "{unknown_placeholder}",
        "{created",
        "{}",
    ],
)
def test_template_with_an_invalid_or_unknown_placeholder_is_rejected(bad_template):
    with pytest.raises(Exception):
        DailyReportSettingsUpdate(daily_report_template={"en": bad_template})


def test_template_language_outside_en_ru_th_is_rejected():
    with pytest.raises(Exception):
        DailyReportSettingsUpdate(daily_report_template={"fr": "Bonjour {created}"})
