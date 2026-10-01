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


def _sample_values():
    return dict(date="2026-01-01", created=3, closed=1, open=5, overdue=0, waiting=0, critical=0, url="https://x")


def test_render_daily_report_uses_the_builtin_template_with_no_override():
    org = Organization(name="Org")
    assert notifications.render_daily_report(org, "en", **_sample_values()) == notifications.render("daily_report", "en", **_sample_values())


def test_render_daily_report_prefers_the_organizations_custom_template_for_that_language():
    org = Organization(name="Org", daily_report_template={"en": "{created} new today, {closed} closed."})

    text = notifications.render_daily_report(org, "en", **_sample_values())

    assert text == "3 new today, 1 closed."


def test_render_daily_report_custom_template_is_per_language():
    org = Organization(name="Org", daily_report_template={"en": "Custom EN"})

    assert notifications.render_daily_report(org, "en", **_sample_values()) == "Custom EN"
    assert notifications.render_daily_report(org, "ru", **_sample_values()) == notifications.render("daily_report", "ru", **_sample_values())


def test_render_daily_report_falls_back_on_a_bad_template_at_render_time():
    org = Organization(name="Org", daily_report_template={"en": "{this_placeholder_does_not_exist}"})

    text = notifications.render_daily_report(org, "en", **_sample_values())

    assert text == notifications.render("daily_report", "en", **_sample_values())


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


def test_notify_managers_approval_needed_reaches_every_manager_in_their_language(db_session, monkeypatch):
    from app import notifications as notif_module
    from app.models import Organization, Ticket, TicketPriority, TicketStatus, UserRole

    calls = []
    monkeypatch.setattr(notif_module, "send_message", lambda channel, recipient, text: calls.append((recipient, text)) or True)

    org = Organization(name="Org")
    db_session.add(org)
    db_session.flush()
    channel = Channel(organization_id=org.id, type="telegram", account_id="a" + uuid.uuid4().hex[:8], name="Bot", status="connected", credentials={"bot_token": "x"})
    db_session.add(channel)
    db_session.flush()

    def make(role, chat_id, lang):
        u = User(organization_id=org.id, email=f"{role.value}-{uuid.uuid4().hex[:6]}@example.com", password_hash="h", role=role, telegram_chat_id=chat_id, telegram_channel_id=channel.id, notify_language=lang)
        db_session.add(u)
        return u

    owner = make(UserRole.OWNER, "1", "en")
    manager = make(UserRole.MANAGER, "2", "ru")
    make(UserRole.STAFF, "3", "en")  # not a manager — must not be notified
    unlinked_admin = User(organization_id=org.id, email="admin@example.com", password_hash="h", role=UserRole.ADMIN)
    db_session.add(unlinked_admin)
    db_session.commit()

    ticket = Ticket(organization_id=org.id, title="Roof leak", description="x", priority=TicketPriority.CRITICAL, status=TicketStatus.WAITING_APPROVAL)
    db_session.add(ticket)
    db_session.commit()

    notif_module.notify_managers_approval_needed(db_session, ticket)

    recipients = {r for r, _ in calls}
    assert recipients == {"1", "2"}
    en_text = next(t for r, t in calls if r == "1")
    ru_text = next(t for r, t in calls if r == "2")
    assert "needs your approval" in en_text and "Critical" in en_text and "Roof leak" in en_text
    assert "подтверждение" in ru_text and "Критичный" in ru_text
