import uuid
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from app import daily_report_scheduler as scheduler
from app.models import Channel, Organization, User, UserRole

BANGKOK = ZoneInfo("Asia/Bangkok")
MOSCOW = ZoneInfo("Europe/Moscow")


def make_org(db_session, **overrides):
    values = dict(name="Org", daily_report_enabled=True, daily_report_time="08:00", daily_report_timezone="Asia/Bangkok")
    values.update(overrides)
    org = Organization(**values)
    db_session.add(org)
    db_session.commit()
    return org


def make_channel(db_session, org):
    channel = Channel(organization_id=org.id, type="telegram", account_id="a" + uuid.uuid4().hex[:8], name="Bot", status="connected", credentials={"bot_token": "x"})
    db_session.add(channel)
    db_session.commit()
    return channel


def make_user(db_session, org, role, chat_id=None, channel=None, lang="en"):
    user = User(
        organization_id=org.id,
        email=f"{role.value}-{uuid.uuid4().hex[:6]}@example.com",
        password_hash="h",
        role=role,
        telegram_chat_id=chat_id,
        telegram_channel_id=channel.id if channel else None,
        notify_language=lang,
    )
    db_session.add(user)
    db_session.commit()
    return user


def at_bangkok(y, m, d, h, mi=0):
    return datetime(y, m, d, h, mi, tzinfo=BANGKOK).astimezone(ZoneInfo("UTC"))


def due_ids(db_session, now_utc):
    # The test DB is shared and not rolled back between tests/files, so other tests' orgs may
    # also be "due" at any given instant — every assertion here checks for *our* org's presence
    # rather than asserting the full list, which would be flaky depending on test order.
    return {o.id for o in scheduler._due_orgs(db_session, now_utc)}


def test_an_org_before_its_send_time_is_not_due(db_session):
    org = make_org(db_session, daily_report_time="08:00")
    assert org.id not in due_ids(db_session, at_bangkok(2026, 6, 15, 7, 59))


def test_an_org_at_or_after_its_send_time_is_due(db_session):
    org = make_org(db_session, daily_report_time="08:00")
    assert org.id in due_ids(db_session, at_bangkok(2026, 6, 15, 8, 0))
    assert org.id in due_ids(db_session, at_bangkok(2026, 6, 15, 14, 0))


def test_disabled_orgs_are_never_due(db_session):
    org = make_org(db_session, daily_report_enabled=False, daily_report_time="00:00")
    assert org.id not in due_ids(db_session, at_bangkok(2026, 6, 15, 12, 0))


def test_an_org_already_sent_today_is_not_due_again(db_session):
    org = make_org(db_session, daily_report_time="08:00", daily_report_last_sent_date=date(2026, 6, 15))
    assert org.id not in due_ids(db_session, at_bangkok(2026, 6, 15, 20, 0))


def test_a_new_local_day_makes_it_due_again(db_session):
    org = make_org(db_session, daily_report_time="08:00", daily_report_last_sent_date=date(2026, 6, 15))
    assert org.id in due_ids(db_session, at_bangkok(2026, 6, 16, 8, 0))


def test_timezones_are_evaluated_independently(db_session):
    # 08:00 Moscow (UTC+3) is 12:00 Bangkok (UTC+7); at 09:00 Bangkok time only the Bangkok org is due.
    bkk = make_org(db_session, daily_report_time="08:00", daily_report_timezone="Asia/Bangkok")
    msk = make_org(db_session, daily_report_time="08:00", daily_report_timezone="Europe/Moscow")

    due = due_ids(db_session, at_bangkok(2026, 6, 15, 9, 0))

    assert bkk.id in due
    assert msk.id not in due


def test_an_unknown_timezone_is_skipped_not_crashed(db_session):
    org = make_org(db_session, daily_report_time="00:00", daily_report_timezone="Mars/OlympusMons")
    assert org.id not in due_ids(db_session, at_bangkok(2026, 6, 15, 12, 0))


def test_run_tick_sends_to_managers_only_and_is_idempotent_same_day(db_session, monkeypatch):
    org = make_org(db_session, daily_report_time="08:00")
    channel = make_channel(db_session, org)
    manager = make_user(db_session, org, UserRole.MANAGER, chat_id="1", channel=channel, lang="ru")
    staff = make_user(db_session, org, UserRole.STAFF, chat_id="2", channel=channel)

    sent_to = []
    monkeypatch.setattr(scheduler, "send_to_user", lambda db, user, text: sent_to.append((user.id, text)) or "sent")

    scheduler.run_tick(db_session, at_bangkok(2026, 6, 15, 9, 0))

    mine = [text for uid, text in sent_to if uid == manager.id]
    assert len(mine) == 1
    assert "сводк" in mine[0].lower()
    assert not any(uid == staff.id for uid, _ in sent_to)
    db_session.refresh(org)
    assert org.daily_report_last_sent_date == date(2026, 6, 15)

    sent_to.clear()
    scheduler.run_tick(db_session, at_bangkok(2026, 6, 15, 18, 0))
    assert not any(uid == manager.id for uid, _ in sent_to)  # already sent today, not repeated


def test_message_is_localized_per_manager_and_carries_a_link(db_session, monkeypatch):
    monkeypatch.setenv("PUBLIC_WEB_URL", "https://app.example.com")
    org = make_org(db_session, daily_report_time="08:00")
    channel = make_channel(db_session, org)
    owner = make_user(db_session, org, UserRole.OWNER, chat_id="1", channel=channel, lang="en")
    manager = make_user(db_session, org, UserRole.MANAGER, chat_id="2", channel=channel, lang="th")

    sent = {}
    monkeypatch.setattr(scheduler, "send_to_user", lambda db, user, text: sent.setdefault(user.id, text) or "sent")

    scheduler.run_tick(db_session, at_bangkok(2026, 6, 15, 8, 30))

    assert "Daily report" in sent[owner.id] and "https://app.example.com/reports/daily?date=" in sent[owner.id]
    assert "สรุปประจำวัน" in sent[manager.id]


def test_orgs_are_processed_independently(db_session, monkeypatch):
    due_org = make_org(db_session, daily_report_time="08:00")
    not_due_org = make_org(db_session, daily_report_time="23:59")
    make_user(db_session, due_org, UserRole.OWNER, chat_id="1", channel=make_channel(db_session, due_org))
    make_user(db_session, not_due_org, UserRole.OWNER, chat_id="2", channel=make_channel(db_session, not_due_org))
    monkeypatch.setattr(scheduler, "send_to_user", lambda db, user, text: "sent")

    scheduler.run_tick(db_session, at_bangkok(2026, 6, 15, 9, 0))

    db_session.refresh(due_org)
    db_session.refresh(not_due_org)
    assert due_org.daily_report_last_sent_date == date(2026, 6, 15)
    assert not_due_org.daily_report_last_sent_date is None
