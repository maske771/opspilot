import hashlib
import hmac
import json
import os
import uuid

from fastapi import APIRouter, Header, HTTPException, Request
from sqlalchemy import text

from .db import SessionLocal

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

PROVIDERS = {"line", "whatsapp", "telegram", "email"}


def verify_signature(body: bytes, signature: str | None) -> bool:
    secret = os.getenv("WEBHOOK_SECRET")
    if not secret:
        return os.getenv("APP_ENV", "development") != "production"
    if not signature:
        return False
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    supplied = signature.removeprefix("sha256=")
    return hmac.compare_digest(expected, supplied)


@router.post("/{provider}/{account_id}")
async def receive_webhook(
    provider: str,
    account_id: str,
    request: Request,
    x_webhook_signature: str | None = Header(default=None),
    x_event_id: str | None = Header(default=None),
):
    provider = provider.strip().lower()
    if provider not in PROVIDERS:
        raise HTTPException(404, "Unsupported webhook provider")
    body = await request.body()
    if not verify_signature(body, x_webhook_signature):
        raise HTTPException(401, "Invalid webhook signature")
    try:
        payload = json.loads(body or b"{}")
    except json.JSONDecodeError as exc:
        raise HTTPException(400, "Webhook payload must be valid JSON") from exc

    db = SessionLocal()
    try:
        channel = db.execute(
            text("SELECT id, organization_id FROM channels WHERE type = :provider AND name = :account_id AND status = 'connected' ORDER BY created_at DESC LIMIT 1"),
            {"provider": provider, "account_id": account_id},
        ).mappings().first()
        if channel is None:
            raise HTTPException(404, "Connected channel not found")
        event_id = x_event_id or payload.get("event_id") or payload.get("id") or str(uuid.uuid4())
        db.execute(
            text("""INSERT INTO webhook_events
                (organization_id, channel_id, provider, account_id, external_event_id, payload, signature_valid)
                VALUES (:org_id, :channel_id, :provider, :account_id, :event_id, CAST(:payload AS jsonb), TRUE)
                ON CONFLICT (organization_id, provider, account_id, external_event_id) DO NOTHING"""),
            {"org_id": channel["organization_id"], "channel_id": channel["id"], "provider": provider,
             "account_id": account_id, "event_id": event_id, "payload": json.dumps(payload)},
        )
        db.commit()
        return {"status": "accepted", "event_id": event_id}
    finally:
        db.close()
