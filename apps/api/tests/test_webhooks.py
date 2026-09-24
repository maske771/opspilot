import hashlib
import hmac

from app.webhook_auth import is_authorized, token_matches, verify_signature


def sign(secret: str, body: bytes) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def test_signature_valid_in_both_forms(monkeypatch):
    monkeypatch.setenv("WEBHOOK_SECRET", "test-secret")
    body = b'{"id":"evt-1"}'
    assert verify_signature(body, sign("test-secret", body))
    assert verify_signature(body, "sha256=" + sign("test-secret", body))


def test_signature_invalid(monkeypatch):
    monkeypatch.setenv("WEBHOOK_SECRET", "test-secret")
    assert not verify_signature(b'{"id":"evt-1"}', "bad")
    assert not verify_signature(b'{"id":"evt-1"}', None)


def test_signature_never_passes_without_a_secret(monkeypatch):
    monkeypatch.delenv("WEBHOOK_SECRET", raising=False)
    for env in ("development", "production"):
        monkeypatch.setenv("APP_ENV", env)
        assert not verify_signature(b"{}", None)
        assert not verify_signature(b"{}", "anything")


def test_token_matches():
    assert token_matches("abc", "abc")
    assert not token_matches("abc", "abd")
    assert not token_matches("abc", None)
    assert not token_matches("abc", "")
    assert not token_matches(None, "abc")
    assert not token_matches("", "")


def test_is_authorized_accepts_any_matching_token(monkeypatch):
    monkeypatch.delenv("WEBHOOK_SECRET", raising=False)
    assert is_authorized("tok", (None, "wrong", "tok"), b"{}", None)
    assert not is_authorized("tok", (None, "wrong"), b"{}", None)
    assert not is_authorized("tok", (), b"{}", None)


def test_is_authorized_accepts_a_valid_signature_instead_of_a_token(monkeypatch):
    monkeypatch.setenv("WEBHOOK_SECRET", "s3cret")
    body = b'{"a":1}'
    assert is_authorized("tok", (None,), body, sign("s3cret", body))
    assert not is_authorized("tok", (None,), body, "nope")
