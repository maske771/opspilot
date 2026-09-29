import string
import uuid

from app import notifications
from app.models import Channel, Organization, Ticket, TicketPriority, User, UserRole


def make_ticket(**overrides) -> Ticket:
    values = dict(id=uuid.uuid4(), title="Air conditioner is broken", description="x", priority=TicketPriority.HIGH)
    values.update(overrides)
    return Ticket(**values)


def test_language_falls_back_to_english():
    assert notifications.normalize_language("ru") == "ru"
    assert notifications.normalize_language("ru-RU") == "ru"
    assert notifications.normalize_language("TH") == "th"
    assert notifications.normalize_language("de") == "en"
    assert notifications.normalize_language(None) == "en"


def test_every_message_exists_in_every_language_with_the_same_placeholders():
    for kind, variants in notifications.MESSAGES.items():
        assert set(variants) == set(notifications.SUPPORTED_LANGUAGES), kind
        fields = {lang: {field for _, field, _, _ in string.Formatter().parse(text) if field} for lang, text in variants.items()}
        assert fields["ru"] == fields["en"] == fields["th"], kind


def test_ticket_message_is_localized_and_carries_the_link(monkeypatch):
    monkeypatch.setenv("PUBLIC_WEB_URL", "https://app.example.com/")
    ticket = make_ticket()

    en = notifications.ticket_message("assigned", ticket, "en", 25)
    ru = notifications.ticket_message("assigned", ticket, "ru", 25)
    th = notifications.ticket_message("assigned", ticket, "th", 25)

    assert "High" in en and "25 min" in en
    assert "Высокий" in ru and "25 мин" in ru
    assert "สูง" in th and "25" in th
    assert all(f"https://app.example.com/tickets/{ticket.id}" in text for text in (en, ru, th))
    assert all("Air conditioner is broken" in text for text in (en, ru, th))


def test_ticket_message_without_a_public_url_has_no_dangling_line(monkeypatch):
    monkeypatch.delenv("PUBLIC_WEB_URL", raising=False)
    text = notifications.ticket_message("response_overdue", make_ticket(), "en", 7)
    assert text == "Response overdue by 7 min: Air conditioner is broken"


def test_minutes_are_never_zero_or_negative():
    assert "1 min" in notifications.ticket_message("response_soon", make_ticket(), "en", 0)


def test_title_with_braces_is_not_treated_as_a_template():
    text = notifications.ticket_message("response_soon", make_ticket(title="Leak {minutes} {url}"), "en", 3)
    assert "Leak {minutes} {url}" in text


def test_escalation_names_the_assignee_or_says_nobody(monkeypatch):
    monkeypatch.delenv("PUBLIC_WEB_URL", raising=False)
    assignee = User(email="anna.k@example.com", role=UserRole.TECHNICIAN)
    assert "Assignee: anna.k." in notifications.ticket_message("escalation_response", make_ticket(), "en", 5, assignee)
    assert "nobody assigned" in notifications.ticket_message("escalation_response", make_ticket(), "en", 5)
    assert "не назначен" in notifications.ticket_message("escalation_resolution", make_ticket(), "ru", 5)


def make_linked_user(db_session, channel_status="connected", channel_type="telegram", linked=True):
    org = Organization(name="Org")
    db_session.add(org)
    db_session.flush()
    channel = Channel(organization_id=org.id, type=channel_type, account_id="a" + uuid.uuid4().hex[:8], name="Bot", status=channel_status, credentials={"bot_token": "x"})
    db_session.add(channel)
    db_session.flush()
    user = User(
        organization_id=org.id,
        email=f"u-{uuid.uuid4().hex[:8]}@example.com",
        password_hash="h",
        role=UserRole.TECHNICIAN,
        telegram_chat_id="555" if linked else None,
        telegram_channel_id=channel.id if linked else None,
    )
    db_session.add(user)
    db_session.commit()
    return user


def test_send_to_user_skips_unlinked_users_without_calling_telegram(db_session, monkeypatch):
    monkeypatch.setattr(notifications, "send_message", lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not send")))
    user = make_linked_user(db_session, linked=False)
    assert notifications.send_to_user(db_session, user, "hi") == notifications.SKIPPED


def test_send_to_user_skips_when_the_bot_is_gone(db_session, monkeypatch):
    monkeypatch.setattr(notifications, "send_message", lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not send")))
    assert notifications.send_to_user(db_session, make_linked_user(db_session, channel_status="disconnected"), "hi") == notifications.SKIPPED
    assert notifications.send_to_user(db_session, make_linked_user(db_session, channel_type="line"), "hi") == notifications.SKIPPED


def test_send_to_user_reports_sent_and_failed(db_session, monkeypatch):
    calls = []
    outcome = {"ok": True}

    def fake_send(channel, recipient, text):
        calls.append((recipient, text))
        return outcome["ok"]

    monkeypatch.setattr(notifications, "send_message", fake_send)
    user = make_linked_user(db_session)

    assert notifications.send_to_user(db_session, user, "hello") == notifications.SENT
    assert calls == [("555", "hello")]
    outcome["ok"] = False
    assert notifications.send_to_user(db_session, user, "hello") == notifications.FAILED
