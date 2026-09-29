import logging
import os
from urllib.parse import quote

import httpx
from sqlalchemy import select

from .db import SessionLocal
from .models import Channel
from .telegram_api import api_base

logger = logging.getLogger("opspilot.telegram_webhook")


def webhook_url(channel: Channel) -> str | None:
    base = os.getenv("PUBLIC_API_URL")
    if not base:
        return None
    return f"{base.rstrip('/')}/webhooks/{channel.type}/{quote(channel.account_id, safe='')}?token={channel.webhook_token}"


def register_telegram_webhook(channel: Channel) -> bool:
    """Point the bot's webhook at this channel. Never raises, and never logs the URL:
    httpx errors embed the request URL, which contains the bot token."""
    bot_token = (channel.credentials or {}).get("bot_token")
    url = webhook_url(channel)
    if channel.type != "telegram" or not bot_token or not url:
        return False
    try:
        response = httpx.post(
            f"{api_base()}/bot{bot_token}/setWebhook",
            json={"url": url, "secret_token": channel.webhook_token},
            timeout=10,
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        logger.warning("Telegram setWebhook rejected for channel %s: HTTP %s", channel.id, exc.response.status_code)
        return False
    except httpx.HTTPError as exc:
        logger.warning("Telegram setWebhook failed for channel %s: %s", channel.id, type(exc).__name__)
        return False
    logger.info("Registered Telegram webhook for channel %s", channel.id)
    return True


def bot_username(channel: Channel) -> str | None:
    """The bot's @username (for a t.me deep link). Best effort; never raises or logs the token."""
    bot_token = (channel.credentials or {}).get("bot_token")
    if channel.type != "telegram" or not bot_token:
        return None
    try:
        response = httpx.get(f"{api_base()}/bot{bot_token}/getMe", timeout=10)
        response.raise_for_status()
        return response.json()["result"].get("username")
    except (httpx.HTTPError, KeyError, ValueError, TypeError) as exc:
        logger.warning("Telegram getMe failed for channel %s: %s", channel.id, type(exc).__name__)
        return None


def register_all_telegram_webhooks() -> int:
    """Re-register every connected Telegram channel (idempotent). Returns how many succeeded."""
    if not os.getenv("PUBLIC_API_URL"):
        return 0
    registered = 0
    with SessionLocal() as db:
        channels = db.scalars(select(Channel).where(Channel.type == "telegram", Channel.status == "connected")).all()
        for channel in channels:
            if register_telegram_webhook(channel):
                registered += 1
    return registered
