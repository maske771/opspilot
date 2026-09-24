import logging
import uuid

import httpx
import pytest

from app import telegram_webhook
from app.models import Channel


@pytest.fixture(autouse=True)
def propagate_opspilot_logs(monkeypatch):
    # app.main stops "opspilot" records from propagating; caplog listens on the root logger.
    monkeypatch.setattr(logging.getLogger("opspilot"), "propagate", True)


def make_channel(**overrides) -> Channel:
    values = dict(
        id=uuid.uuid4(),
        type="telegram",
        account_id="my bot",
        name="Bot",
        status="connected",
        webhook_token="tok123",
        credentials={"bot_token": "123456:SECRET-BOT-TOKEN"},
    )
    values.update(overrides)
    return Channel(**values)


def test_webhook_url_needs_a_public_base_url(monkeypatch):
    monkeypatch.delenv("PUBLIC_API_URL", raising=False)
    assert telegram_webhook.webhook_url(make_channel()) is None


def test_webhook_url_carries_the_token_and_escapes_the_account_id(monkeypatch):
    monkeypatch.setenv("PUBLIC_API_URL", "https://api.example.com/")
    assert telegram_webhook.webhook_url(make_channel()) == "https://api.example.com/webhooks/telegram/my%20bot?token=tok123"


def test_register_sends_url_and_secret_token(monkeypatch):
    monkeypatch.setenv("PUBLIC_API_URL", "https://api.example.com")
    calls = []

    def fake_post(url, json, timeout):
        calls.append((url, json))
        return httpx.Response(200, json={"ok": True}, request=httpx.Request("POST", url))

    monkeypatch.setattr(telegram_webhook.httpx, "post", fake_post)

    assert telegram_webhook.register_telegram_webhook(make_channel()) is True
    url, payload = calls[0]
    assert url == "https://api.telegram.org/bot123456:SECRET-BOT-TOKEN/setWebhook"
    assert payload == {"url": "https://api.example.com/webhooks/telegram/my%20bot?token=tok123", "secret_token": "tok123"}


def test_register_skips_when_not_applicable(monkeypatch):
    monkeypatch.setenv("PUBLIC_API_URL", "https://api.example.com")
    monkeypatch.setattr(telegram_webhook.httpx, "post", lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not call Telegram")))

    assert telegram_webhook.register_telegram_webhook(make_channel(credentials=None)) is False
    assert telegram_webhook.register_telegram_webhook(make_channel(type="line")) is False
    monkeypatch.delenv("PUBLIC_API_URL")
    assert telegram_webhook.register_telegram_webhook(make_channel()) is False


def test_register_failure_does_not_raise_or_leak_the_bot_token(monkeypatch, caplog):
    monkeypatch.setenv("PUBLIC_API_URL", "https://api.example.com")

    def rejected(url, json, timeout):
        return httpx.Response(401, request=httpx.Request("POST", url))

    monkeypatch.setattr(telegram_webhook.httpx, "post", rejected)
    with caplog.at_level(logging.DEBUG, logger="opspilot.telegram_webhook"):
        assert telegram_webhook.register_telegram_webhook(make_channel()) is False
    assert "401" in caplog.text
    assert "SECRET-BOT-TOKEN" not in caplog.text
    assert "tok123" not in caplog.text


def test_register_network_error_does_not_raise_or_leak(monkeypatch, caplog):
    monkeypatch.setenv("PUBLIC_API_URL", "https://api.example.com")

    def down(url, json, timeout):
        raise httpx.ConnectError("boom", request=httpx.Request("POST", url))

    monkeypatch.setattr(telegram_webhook.httpx, "post", down)
    with caplog.at_level(logging.DEBUG, logger="opspilot.telegram_webhook"):
        assert telegram_webhook.register_telegram_webhook(make_channel()) is False
    assert "ConnectError" in caplog.text
    assert "SECRET-BOT-TOKEN" not in caplog.text
