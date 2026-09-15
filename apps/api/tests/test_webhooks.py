import hashlib
import hmac
import os

from app.webhook_routes import verify_signature


def test_webhook_signature_valid(monkeypatch):
    monkeypatch.setenv("WEBHOOK_SECRET", "test-secret")
    body = b'{"id":"evt-1"}'
    signature = hmac.new(b"test-secret", body, hashlib.sha256).hexdigest()
    assert verify_signature(body, signature)
    assert verify_signature(body, "sha256=" + signature)


def test_webhook_signature_invalid(monkeypatch):
    monkeypatch.setenv("WEBHOOK_SECRET", "test-secret")
    assert not verify_signature(b'{"id":"evt-1"}', "bad")


def test_webhook_requires_secret_in_production(monkeypatch):
    monkeypatch.delenv("WEBHOOK_SECRET", raising=False)
    monkeypatch.setenv("APP_ENV", "production")
    assert not verify_signature(b"{}", None)


def test_webhook_without_secret_is_allowed_only_for_development(monkeypatch):
    monkeypatch.delenv("WEBHOOK_SECRET", raising=False)
    monkeypatch.setenv("APP_ENV", "development")
    assert verify_signature(b"{}", None)
