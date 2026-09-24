import hashlib
import hmac
import os
from collections.abc import Iterable


def verify_signature(body: bytes, signature: str | None) -> bool:
    """HMAC-SHA256 of the raw body with WEBHOOK_SECRET. Never passes when the secret is unset."""
    secret = os.getenv("WEBHOOK_SECRET")
    if not secret or not signature:
        return False
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature.removeprefix("sha256="))


def token_matches(expected: str | None, supplied: str | None) -> bool:
    if not expected or not supplied:
        return False
    return hmac.compare_digest(expected.encode(), supplied.encode())


def is_authorized(expected_token: str | None, supplied_tokens: Iterable[str | None], body: bytes, signature: str | None) -> bool:
    return any(token_matches(expected_token, supplied) for supplied in supplied_tokens) or verify_signature(body, signature)
