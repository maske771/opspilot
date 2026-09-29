import re
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app import notifications, profile_routes, staff_link, webhook_routes
from app.main import app
from app.models import Channel, Organization, Ticket, TicketPriority, TicketStatus, User, UserRole
from app.staff_link import CODE_ALPHABET, LinkCommand, complete_link, issue_link_code, open_ticket_count, parse_link_command, unlink

NOW = datetime.now(timezone.utc)
TOKEN = "tok-" + uuid.uuid4().hex


def make_org(db_session, *, bot=True):
    org = Organization(name="Org")
    db_session.add(org)
    db_session.flush()
    channel = None
    if bot:
        channel = Channel(organization_id=org.id, type="telegram", account_id="acc-" + uuid.uuid4().hex[:10], name="Bot", status="connected", credentials={"bot_token": "x"}, webhook_token=TOKEN)
        db_session.add(channel)
    db_session.commit()
    return org, channel


def make_user(db_session, org, role=UserRole.TECHNICIAN):
    user = User(organization_id=org.id, email=f"{role.value}-{uuid.uuid4().hex[:6]}@example.com", password_hash="h", role=role)
    db_session.add(user)
    db_session.commit()
    return user


def message(text, *, chat_type="private", chat_id=555, language="th"):
    return {"message": {"message_id": 1, "text": text, "chat": {"id": chat_id, "type": chat_type}, "from": {"id": 9, "language_code": language}}}


# ---- code issuing / parsing / completing

def test_issued_codes_are_short_unambiguous_and_expire(db_session):
    org, _ = make_org(db_session)
    user = make_user(db_session, org)

    code, expires_at = issue_link_code(db_session, user, NOW)

    assert len(code) == 8 and set(code) <= set(CODE_ALPHABET)
    assert not set(code) & set("01OI")
    assert expires_at == NOW + timedelta(minutes=10)
    assert user.telegram_link_code == code


def test_a_new_code_replaces_the_old_one(db_session):
    org, _ = make_org(db_session)
    user = make_user(db_session, org)
    first, _ = issue_link_code(db_session, user)
    second, _ = issue_link_code(db_session, user)
    assert first != second and user.telegram_link_code == second


@pytest.mark.parametrize(
    "text",
    ["/link ABCD2345", "/start ABCD2345", "/link@my_bot ABCD2345", "  /link   ABCD2345  ", "/link abcd2345"],
)
def test_parses_link_commands(text):
    command = parse_link_command(message(text))
    assert command == LinkCommand(chat_id="555", code="ABCD2345", language="th")


@pytest.mark.parametrize("text", ["/link", "/start", "hello", "/link ABC", "/help ABCD2345", "link ABCD2345", "/link ABCD2345 extra"])
def test_ignores_everything_else(text):
    assert parse_link_command(message(text)) is None


def test_only_private_chats_can_link():
    assert parse_link_command(message("/link ABCD2345", chat_type="group")) is None
    assert parse_link_command({"message": {"text": "/link ABCD2345", "chat": {"id": 1}}}) is None
    assert parse_link_command({}) is None


def test_language_comes_from_telegram_and_falls_back_to_english():
    assert parse_link_command(message("/link ABCD2345", language="ru-RU")).language == "ru"
    assert parse_link_command(message("/link ABCD2345", language="de")).language == "en"


def test_complete_link_binds_the_chat_and_consumes_the_code(db_session):
    org, channel = make_org(db_session)
    user = make_user(db_session, org)
    code, _ = issue_link_code(db_session, user, NOW)

    linked = complete_link(db_session, org.id, channel.id, LinkCommand("555", code, "ru"), NOW)
    db_session.commit()

    assert linked.id == user.id
    assert (user.telegram_chat_id, user.telegram_channel_id, user.notify_language) == ("555", channel.id, "ru")
    assert user.telegram_link_code is None and user.telegram_linked
    assert complete_link(db_session, org.id, channel.id, LinkCommand("777", code, "en"), NOW) is None  # single use


def test_expired_codes_are_rejected(db_session):
    org, channel = make_org(db_session)
    user = make_user(db_session, org)
    code, _ = issue_link_code(db_session, user, NOW - timedelta(minutes=11))

    assert complete_link(db_session, org.id, channel.id, LinkCommand("555", code, "en"), NOW) is None
    assert not user.telegram_linked


def test_a_code_only_works_in_its_own_organization(db_session):
    org, _ = make_org(db_session)
    other, other_channel = make_org(db_session)
    user = make_user(db_session, org)
    code, _ = issue_link_code(db_session, user, NOW)

    assert complete_link(db_session, other.id, other_channel.id, LinkCommand("555", code, "en"), NOW) is None
    assert not user.telegram_linked


def test_unlink_clears_everything(db_session):
    org, channel = make_org(db_session)
    user = make_user(db_session, org)
    code, _ = issue_link_code(db_session, user, NOW)
    complete_link(db_session, org.id, channel.id, LinkCommand("555", code, "en"), NOW)
    db_session.commit()

    unlink(db_session, user)

    assert (user.telegram_chat_id, user.telegram_channel_id, user.telegram_link_code) == (None, None, None)
    assert not user.telegram_linked


def test_open_ticket_count_ignores_finished_work(db_session):
    org, _ = make_org(db_session)
    user = make_user(db_session, org)
    for status in (TicketStatus.ASSIGNED, TicketStatus.IN_PROGRESS, TicketStatus.COMPLETED, TicketStatus.CLOSED):
        db_session.add(Ticket(organization_id=org.id, title="t", description="x", priority=TicketPriority.LOW, status=status, assignee_id=user.id))
    db_session.commit()
    assert open_ticket_count(db_session, user) == 2


# ---- /me endpoints

def test_link_code_needs_a_connected_telegram_bot(db_session):
    org, _ = make_org(db_session, bot=False)
    user = make_user(db_session, org)

    assert profile_routes.telegram_status(user=user, db=db_session).channel_available is False
    with pytest.raises(HTTPException) as exc:
        profile_routes.create_telegram_link_code(user=user, db=db_session)
    assert exc.value.status_code == 409


def test_link_code_endpoint_returns_a_code_and_a_deep_link(db_session, monkeypatch):
    monkeypatch.setattr(profile_routes, "bot_username", lambda channel: "opspilot_bot")
    org, _ = make_org(db_session)
    user = make_user(db_session, org)

    result = profile_routes.create_telegram_link_code(user=user, db=db_session)

    assert result.deep_link == f"https://t.me/opspilot_bot?start={result.code}"
    assert profile_routes.telegram_status(user=user, db=db_session).channel_available is True
    assert profile_routes.telegram_status(user=user, db=db_session).linked is False


def test_deep_link_is_omitted_when_the_bot_name_is_unknown(db_session, monkeypatch):
    monkeypatch.setattr(profile_routes, "bot_username", lambda channel: None)
    org, _ = make_org(db_session)
    assert profile_routes.create_telegram_link_code(user=make_user(db_session, org), db=db_session).deep_link is None


def test_a_disconnected_bot_does_not_count(db_session):
    org, channel = make_org(db_session)
    channel.status = "disconnected"
    db_session.commit()
    assert profile_routes.telegram_status(user=make_user(db_session, org), db=db_session).channel_available is False


# ---- the /link command through the real webhook route

@pytest.fixture
def client(db_session, webhook_events_table, monkeypatch):
    monkeypatch.delenv("WEBHOOK_SECRET", raising=False)
    monkeypatch.setattr(webhook_routes, "SessionLocal", sessionmaker(bind=db_session.get_bind(), expire_on_commit=False))
    sent = []
    monkeypatch.setattr(webhook_routes, "send_message", lambda channel, recipient, text: sent.append((recipient, text)) or True)
    test_client = TestClient(app)
    test_client.sent = sent
    return test_client


def send_command(client, channel, text, **kwargs):
    return client.post(f"/webhooks/telegram/{channel.account_id}", params={"token": TOKEN}, json=message(text, **kwargs))


def test_link_command_links_the_sender_and_replies_in_their_language(db_session, client):
    org, channel = make_org(db_session)
    user = make_user(db_session, org)
    db_session.add(Ticket(organization_id=org.id, title="t", description="x", priority=TicketPriority.LOW, status=TicketStatus.ASSIGNED, assignee_id=user.id))
    db_session.commit()
    code, _ = issue_link_code(db_session, user)

    response = send_command(client, channel, f"/link {code}", chat_id=4242, language="th")

    assert response.status_code == 200 and response.json()["linked"] is True
    db_session.refresh(user)
    assert user.telegram_chat_id == "4242" and user.notify_language == "th"
    recipient, text = client.sent[0]
    assert recipient == "4242" and user.email in text and "เชื่อมต่อ Telegram" in text and "1" in text


def test_start_deep_link_payload_works_too(db_session, client):
    org, channel = make_org(db_session)
    user = make_user(db_session, org)
    code, _ = issue_link_code(db_session, user)

    assert send_command(client, channel, f"/start {code}").json()["linked"] is True


def test_wrong_code_gets_a_polite_refusal_and_links_nobody(db_session, client):
    org, channel = make_org(db_session)
    user = make_user(db_session, org)
    issue_link_code(db_session, user)

    response = send_command(client, channel, "/link ZZZZZZZZ", language="ru")

    assert response.json()["linked"] is False
    assert "недействителен" in client.sent[0][1]
    db_session.refresh(user)
    assert not user.telegram_linked


def test_a_link_command_never_creates_a_customer_ticket(db_session, client):
    org, channel = make_org(db_session)
    make_user(db_session, org)
    send_command(client, channel, "/link ZZZZZZZZ")

    assert db_session.query(Ticket).filter(Ticket.organization_id == org.id).count() == 0


def test_the_command_still_needs_the_channel_token(db_session, client):
    org, channel = make_org(db_session)
    user = make_user(db_session, org)
    code, _ = issue_link_code(db_session, user)

    response = client.post(f"/webhooks/telegram/{channel.account_id}", json=message(f"/link {code}"))

    assert response.status_code == 401
    db_session.refresh(user)
    assert not user.telegram_linked


def test_ordinary_messages_still_create_tickets(db_session, client):
    org, channel = make_org(db_session)

    response = send_command(client, channel, "The air conditioner is broken")

    assert response.status_code == 200 and response.json().get("ticket_created") is True
    assert re.match(r"^[0-9a-f-]{36}$", response.json()["ticket_id"])
