import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app import sla_monitor
from app.models import Channel, Organization, Ticket, TicketNotification, TicketPriority, TicketStatus, User, UserRole
from app.notifications import FAILED, SENT, SKIPPED

NOW = datetime.now(timezone.utc)


class Org:
    """One organization with a bot, an owner, a manager and a technician (all linked to Telegram)."""

    def __init__(self, db_session, linked=True):
        self.db = db_session
        org = Organization(name="Org")
        db_session.add(org)
        db_session.flush()
        self.org = org
        channel = Channel(organization_id=org.id, type="telegram", account_id="a" + uuid.uuid4().hex[:8], name="Bot", credentials={"bot_token": "x"})
        db_session.add(channel)
        db_session.flush()
        self.owner = self.user(UserRole.OWNER, channel, linked)
        self.manager = self.user(UserRole.MANAGER, channel, linked)
        self.tech = self.user(UserRole.TECHNICIAN, channel, linked)
        db_session.commit()

    def user(self, role, channel, linked=True):
        user = User(
            organization_id=self.org.id,
            email=f"{role.value}-{uuid.uuid4().hex[:6]}@example.com",
            password_hash="h",
            role=role,
            telegram_chat_id=str(uuid.uuid4().int % 10**9) if linked else None,
            telegram_channel_id=channel.id if linked else None,
        )
        self.db.add(user)
        self.db.flush()
        return user

    def ticket(self, *, priority=TicketPriority.HIGH, status=TicketStatus.ASSIGNED, age=timedelta(0), assignee="tech", response_min=30, resolution_min=240, **extra):
        created = NOW - age
        ticket = Ticket(
            organization_id=self.org.id,
            title="Leak in villa 3",
            description="x",
            priority=priority,
            status=status,
            assignee_id=getattr(self, assignee).id if assignee else None,
            created_at=created,
            response_deadline=created + timedelta(minutes=response_min),
            resolution_deadline=created + timedelta(minutes=resolution_min),
            **extra,
        )
        self.db.add(ticket)
        self.db.commit()
        return ticket


@pytest.fixture
def sent(monkeypatch):
    """Replace Telegram delivery: linked users get SENT, unlinked SKIPPED; failures can be forced per user."""
    log = []
    forced_failures = set()

    def fake(db, user, text):
        if not user.telegram_linked:
            return SKIPPED
        if user.id in forced_failures:
            return FAILED
        log.append((user.id, text))
        return SENT

    monkeypatch.setattr(sla_monitor, "send_to_user", fake)
    fake.log = log
    fake.fail_for = forced_failures.add
    fake.recover = forced_failures.clear
    return fake


def kinds(db, *tickets):
    rows = db.scalars(select(TicketNotification).where(TicketNotification.ticket_id.in_([t.id for t in tickets]))).all()
    return {(r.user_id, r.kind): r for r in rows}


def tick(db):
    return sla_monitor.run_tick(db, NOW)


def test_new_assignment_notifies_the_assignee_once(db_session, sent):
    org = Org(db_session)
    ticket = org.ticket()

    tick(db_session)
    tick(db_session)
    tick(db_session)

    rows = kinds(db_session, ticket)
    assert (org.tech.id, "assigned") in rows and rows[(org.tech.id, "assigned")].status == "sent"
    mine = [text for uid, text in sent.log if uid == org.tech.id and "Leak in villa 3" in text and "New ticket assigned" in text]
    assert len(mine) == 1


def test_unassigned_tickets_do_not_announce_an_assignment(db_session, sent):
    org = Org(db_session)
    ticket = org.ticket(assignee=None, status=TicketStatus.NEW)

    tick(db_session)

    assert not any(kind == "assigned" for _, kind in kinds(db_session, ticket))


def test_warns_the_assignee_shortly_before_the_response_deadline(db_session, sent):
    org = Org(db_session)
    ticket = org.ticket(priority=TicketPriority.CRITICAL, age=timedelta(minutes=13), response_min=15, resolution_min=60)

    tick(db_session)

    rows = kinds(db_session, ticket)
    assert (org.tech.id, "response_soon") in rows
    assert not any(k.startswith("escalation") or k.endswith("overdue") for _, k in rows)


def test_no_early_warning_when_the_deadline_is_far(db_session, sent):
    org = Org(db_session)
    ticket = org.ticket(age=timedelta(minutes=1), response_min=30)

    tick(db_session)

    assert not any(k.endswith("soon") for _, k in kinds(db_session, ticket))


def test_response_overdue_notifies_assignee_and_escalates_to_managers(db_session, sent):
    org = Org(db_session)
    ticket = org.ticket(age=timedelta(hours=2), response_min=30, resolution_min=600)

    tick(db_session)

    rows = kinds(db_session, ticket)
    assert (org.tech.id, "response_overdue") in rows
    assert (org.manager.id, "escalation_response") in rows
    assert (org.owner.id, "escalation_response") in rows
    assert (org.tech.id, "escalation_response") not in rows
    escalation = next(text for uid, text in sent.log if uid == org.manager.id and "Escalation" in text)
    assert "Assignee: technician-" in escalation


def test_unassigned_overdue_ticket_escalates_to_managers_only(db_session, sent):
    org = Org(db_session)
    ticket = org.ticket(assignee=None, status=TicketStatus.NEW, age=timedelta(hours=3), response_min=30, resolution_min=600)

    tick(db_session)

    rows = kinds(db_session, ticket)
    assert (org.manager.id, "escalation_response") in rows
    assert not any(uid == org.tech.id for uid, _ in rows)
    assert any("nobody assigned" in text for uid, text in sent.log if uid == org.manager.id)


def test_an_assignee_who_is_also_a_manager_gets_one_message_not_two(db_session, sent):
    org = Org(db_session)
    ticket = org.ticket(assignee="manager", age=timedelta(hours=2), response_min=30, resolution_min=600)

    tick(db_session)

    rows = kinds(db_session, ticket)
    assert (org.manager.id, "response_overdue") in rows
    assert (org.manager.id, "escalation_response") not in rows


def test_once_accepted_only_the_resolution_deadline_matters(db_session, sent):
    org = Org(db_session)
    ticket = org.ticket(status=TicketStatus.ACCEPTED, age=timedelta(hours=2), response_min=30, resolution_min=600)

    tick(db_session)

    assert not any(k.startswith("response") or k == "escalation_response" for _, k in kinds(db_session, ticket))

    late = org.ticket(status=TicketStatus.IN_PROGRESS, age=timedelta(hours=10), response_min=30, resolution_min=240)
    tick(db_session)
    late_rows = kinds(db_session, late)
    assert (org.tech.id, "resolution_overdue") in late_rows
    assert (org.manager.id, "escalation_resolution") in late_rows


@pytest.mark.parametrize("status", [TicketStatus.COMPLETED, TicketStatus.CLOSED, TicketStatus.WAITING_APPROVAL])
def test_finished_tickets_are_left_alone(db_session, sent, status):
    org = Org(db_session)
    ticket = org.ticket(status=status, age=timedelta(hours=10), response_min=30, resolution_min=60)

    tick(db_session)

    assert kinds(db_session, ticket) == {}


def test_history_is_not_replayed(db_session, sent):
    org = Org(db_session)
    long_overdue = org.ticket(age=timedelta(days=3), response_min=30, resolution_min=120)
    old_assignment = org.ticket(age=timedelta(hours=60), response_min=30 * 60, resolution_min=10 * 60 * 60)

    tick(db_session)

    assert kinds(db_session, long_overdue) == {}
    assert not any(kind == "assigned" for _, kind in kinds(db_session, old_assignment))


def test_recipients_who_are_not_linked_are_recorded_and_never_retried(db_session, sent):
    org = Org(db_session, linked=False)
    ticket = org.ticket(age=timedelta(hours=2), response_min=30, resolution_min=600)

    tick(db_session)
    rows = kinds(db_session, ticket)
    assert rows and all(row.status == "skipped" for row in rows.values())

    channel = db_session.scalar(select(Channel).where(Channel.organization_id == org.org.id))
    org.tech.telegram_chat_id, org.tech.telegram_channel_id = "999", channel.id
    db_session.commit()
    mine = {org.owner.id, org.manager.id, org.tech.id}
    before = len([1 for uid, _ in sent.log if uid in mine])
    tick(db_session)
    assert len([1 for uid, _ in sent.log if uid in mine]) == before


def test_failed_sends_are_retried_then_given_up(db_session, sent):
    org = Org(db_session)
    ticket = org.ticket()
    sent.fail_for(org.tech.id)

    for _ in range(sla_monitor.MAX_ATTEMPTS + 2):
        tick(db_session)

    row = kinds(db_session, ticket)[(org.tech.id, "assigned")]
    assert row.status == "failed" and row.attempts == sla_monitor.MAX_ATTEMPTS


def test_a_failed_send_that_recovers_is_delivered_once(db_session, sent):
    org = Org(db_session)
    ticket = org.ticket()
    sent.fail_for(org.tech.id)
    tick(db_session)
    sent.recover()

    tick(db_session)
    tick(db_session)

    row = kinds(db_session, ticket)[(org.tech.id, "assigned")]
    assert row.status == "sent" and row.attempts == 2
    assert len([1 for uid, text in sent.log if uid == org.tech.id and "New ticket assigned" in text]) == 1


def test_organizations_are_isolated(db_session, sent):
    first, second = Org(db_session), Org(db_session)
    ticket = first.ticket(age=timedelta(hours=2), response_min=30, resolution_min=600)

    tick(db_session)

    recipients = {uid for uid, _ in kinds(db_session, ticket)}
    assert second.manager.id not in recipients and second.owner.id not in recipients and second.tech.id not in recipients
