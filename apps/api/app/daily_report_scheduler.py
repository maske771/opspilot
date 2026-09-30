import asyncio
import logging
import os
from datetime import datetime, time as time_type
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .db import SessionLocal, engine
from .models import Organization, User
from .notifications import render, send_to_user
from .report_routes import DEFAULT_TIMEZONE, compute_daily_report
from .roles import MANAGER_ROLES

logger = logging.getLogger("opspilot.daily_report")

LOCK_ID = 84210002  # a different Postgres advisory lock than sla_monitor.py's, so both can run at once


def _parse_time(value: str) -> time_type:
    hour, minute = value.split(":")
    return time_type(int(hour), int(minute))


def _due_orgs(db: Session, now_utc: datetime) -> list[Organization]:
    """Organizations with the feature on, past their configured send time today (in their own
    timezone), that haven't had today's report sent yet. A bad/unknown timezone is skipped
    rather than crashing the whole tick."""
    due = []
    for org in db.scalars(select(Organization).where(Organization.daily_report_enabled.is_(True))):
        try:
            tz = ZoneInfo(org.daily_report_timezone or DEFAULT_TIMEZONE)
        except ZoneInfoNotFoundError:
            logger.warning("Organization %s has an unknown timezone %r, skipping", org.id, org.daily_report_timezone)
            continue
        now_local = now_utc.astimezone(tz)
        try:
            target = _parse_time(org.daily_report_time)
        except (ValueError, AttributeError):
            target = time_type(8, 0)
        if now_local.time() >= target and org.daily_report_last_sent_date != now_local.date():
            due.append(org)
    return due


def _send_digest(db: Session, org: Organization) -> None:
    tz = ZoneInfo(org.daily_report_timezone or DEFAULT_TIMEZONE)
    report = compute_daily_report(db, org.id, tz)
    base = os.getenv("PUBLIC_WEB_URL", "").rstrip("/")
    url = f"{base}/reports/daily?date={report.date}" if base else ""
    managers = db.scalars(select(User).where(User.organization_id == org.id, User.role.in_(MANAGER_ROLES)))
    for manager in managers:
        text = render(
            "daily_report",
            manager.notify_language,
            date=report.date,
            created=report.tickets_created,
            closed=report.tickets_closed,
            open=report.currently_open,
            overdue=report.currently_overdue,
            waiting=report.currently_waiting_approval,
            critical=len(report.open_critical_high),
            url=url,
        )
        send_to_user(db, manager, text)


def run_tick(db: Session, now_utc: datetime | None = None) -> int:
    now_utc = now_utc or datetime.now(ZoneInfo("UTC"))
    sent = 0
    for org in _due_orgs(db, now_utc):
        _send_digest(db, org)
        org.daily_report_last_sent_date = now_utc.astimezone(ZoneInfo(org.daily_report_timezone or DEFAULT_TIMEZONE)).date()
        db.commit()  # per org, so one failure doesn't roll back an earlier successful send
        sent += 1
    return sent


def tick_once() -> int:
    with engine.connect() as lock_connection:
        if not lock_connection.execute(select(func.pg_try_advisory_lock(LOCK_ID))).scalar():
            return 0
        try:
            with SessionLocal() as db:
                return run_tick(db)
        finally:
            lock_connection.execute(select(func.pg_advisory_unlock(LOCK_ID)))
            lock_connection.commit()


def scheduler_enabled() -> bool:
    return os.getenv("DAILY_REPORT_WORKER_ENABLED", "true").lower() not in ("0", "false", "no")


async def run_forever() -> None:
    interval = float(os.getenv("DAILY_REPORT_WORKER_INTERVAL_SECONDS", "60"))
    logger.info("Daily report scheduler started (every %ss)", interval)
    while True:
        try:
            sent = await asyncio.to_thread(tick_once)
            if sent:
                logger.info("Daily report scheduler sent %s digest(s)", sent)
        except Exception:
            logger.exception("Daily report scheduler tick failed")
        await asyncio.sleep(interval)
