import json
import uuid

from fastapi import APIRouter, Header, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy import text

from .db import SessionLocal
from .media import download_telegram_photo, save_bytes
from .models import Channel, MessageAttachment
from .outbound import send_message
from .webhook_auth import is_authorized, token_matches
from .webhook_service import ingest_normalized_event, normalize_event

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
PROVIDERS = {"line", "whatsapp", "telegram", "email"}

CHANNEL_LOOKUP = text(
    "SELECT id, organization_id, type, account_id, webhook_token FROM channels "
    "WHERE type = :provider AND account_id = :account_id AND status = 'connected' "
    "ORDER BY created_at DESC LIMIT 1"
)


@router.get("/whatsapp/{account_id}")
def verify_whatsapp(
    account_id: str,
    mode: str | None = Query(default=None, alias="hub.mode"),
    verify_token: str | None = Query(default=None, alias="hub.verify_token"),
    challenge: str | None = Query(default=None, alias="hub.challenge"),
):
    """Meta's webhook verification handshake: echo the challenge when the verify token is this channel's webhook token."""
    with SessionLocal() as db:
        channel = db.execute(CHANNEL_LOOKUP, {"provider": "whatsapp", "account_id": account_id.strip()}).mappings().first()
    if mode != "subscribe" or challenge is None or channel is None or not token_matches(channel["webhook_token"], verify_token):
        raise HTTPException(403, "Verification failed")
    return PlainTextResponse(challenge)


@router.post("/{provider}/{account_id}")
async def receive_webhook(
    provider: str,
    account_id: str,
    request: Request,
    token: str | None = Query(default=None),
    x_webhook_token: str | None = Header(default=None),
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
    x_webhook_signature: str | None = Header(default=None),
    x_event_id: str | None = Header(default=None),
):
    provider = provider.strip().lower()
    account_id = account_id.strip()
    if provider not in PROVIDERS:
        raise HTTPException(404, "Unsupported webhook provider")
    if not account_id:
        raise HTTPException(400, "Account id must not be blank")

    body = await request.body()

    db = SessionLocal()
    try:
        channel = db.execute(CHANNEL_LOOKUP, {"provider": provider, "account_id": account_id}).mappings().first()
        # Same answer for "no such channel" and "bad credentials" so channel ids can't be enumerated.
        if channel is None or not is_authorized(
            channel["webhook_token"], (token, x_webhook_token, x_telegram_bot_api_secret_token), body, x_webhook_signature
        ):
            raise HTTPException(401, "Invalid webhook credentials")

        try:
            payload = json.loads(body or b"{}")
        except json.JSONDecodeError as exc:
            raise HTTPException(400, "Webhook payload must be valid JSON") from exc
        if not isinstance(payload, dict):
            raise HTTPException(400, "Webhook payload must be a JSON object")

        event_id = x_event_id or payload.get("event_id") or payload.get("id") or str(uuid.uuid4())
        result = db.execute(text("""INSERT INTO webhook_events (organization_id, channel_id, provider, account_id, external_event_id, payload, signature_valid)
            VALUES (:org_id, :channel_id, :provider, :account_id, :event_id, CAST(:payload AS jsonb), TRUE)
            ON CONFLICT (organization_id, provider, account_id, external_event_id) DO NOTHING"""),
            {"org_id": channel["organization_id"], "channel_id": channel["id"], "provider": provider, "account_id": account_id, "event_id": event_id, "payload": json.dumps(payload)})
        if result.rowcount == 0:
            db.rollback()
            return {"status": "accepted", "event_id": event_id, "duplicate": True}

        normalized = normalize_event(provider, payload)
        if normalized is None:
            db.commit()
            return {"status": "accepted", "event_id": event_id, "normalized": False}

        data, message_created, ticket_created = ingest_normalized_event(db, channel["organization_id"], channel, normalized)
        db.commit()

        channel_row = db.get(Channel, channel["id"])

        if message_created and normalized.media_file_id and normalized.media_type == "photo" and channel_row is not None and channel_row.credentials:
            bot_token = channel_row.credentials.get("bot_token")
            if bot_token:
                content = download_telegram_photo(bot_token, normalized.media_file_id)
                if content is not None:
                    storage_path = save_bytes(channel["organization_id"], content, ".jpg")
                    db.add(MessageAttachment(
                        organization_id=channel["organization_id"],
                        message_id=data["message_id"],
                        storage_path=storage_path,
                        content_type="image/jpeg",
                    ))
                    db.commit()

        if data["reply_text"] and channel_row is not None:
            send_message(channel_row, normalized.external_user_id, data["reply_text"])

        return {"status": "accepted", "event_id": event_id, "normalized": True, "message_created": message_created, "ticket_created": ticket_created, **data}
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
