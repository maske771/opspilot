import logging
import smtplib
from email.message import EmailMessage
from typing import Any

import httpx

from .models import Channel

logger = logging.getLogger("opspilot.outbound")


def send_message(channel: Channel, recipient: str, text: str) -> bool:
    """Send a text message to `recipient` through `channel`. Never raises —
    a failed or unconfigured channel should not break the caller's flow."""
    if not channel.credentials:
        logger.warning("Channel %s (%s) has no credentials configured, skipping send", channel.id, channel.type)
        return False

    sender = _SENDERS.get(channel.type)
    if sender is None:
        logger.warning("No outbound sender for channel type %s", channel.type)
        return False

    try:
        return sender(channel.credentials, recipient, text)
    except Exception:
        logger.exception("Failed to send message via %s channel %s", channel.type, channel.id)
        return False


def _send_line(credentials: dict[str, Any], recipient: str, text: str) -> bool:
    token = credentials.get("channel_access_token")
    if not token:
        logger.warning("LINE channel missing channel_access_token")
        return False
    response = httpx.post(
        "https://api.line.me/v2/bot/message/push",
        headers={"Authorization": f"Bearer {token}"},
        json={"to": recipient, "messages": [{"type": "text", "text": text}]},
        timeout=10,
    )
    response.raise_for_status()
    return True


def _send_telegram(credentials: dict[str, Any], recipient: str, text: str) -> bool:
    bot_token = credentials.get("bot_token")
    if not bot_token:
        logger.warning("Telegram channel missing bot_token")
        return False
    response = httpx.post(
        f"https://api.telegram.org/bot{bot_token}/sendMessage",
        json={"chat_id": recipient, "text": text},
        timeout=10,
    )
    response.raise_for_status()
    return True


def _send_whatsapp(credentials: dict[str, Any], recipient: str, text: str) -> bool:
    token = credentials.get("access_token")
    phone_number_id = credentials.get("phone_number_id")
    if not token or not phone_number_id:
        logger.warning("WhatsApp channel missing access_token or phone_number_id")
        return False
    response = httpx.post(
        f"https://graph.facebook.com/v20.0/{phone_number_id}/messages",
        headers={"Authorization": f"Bearer {token}"},
        json={"messaging_product": "whatsapp", "to": recipient, "type": "text", "text": {"body": text}},
        timeout=10,
    )
    response.raise_for_status()
    return True


def _send_email(credentials: dict[str, Any], recipient: str, text: str) -> bool:
    host = credentials.get("smtp_host")
    from_address = credentials.get("from_address")
    if not host or not from_address:
        logger.warning("Email channel missing smtp_host or from_address")
        return False
    port = int(credentials.get("smtp_port", 587))
    username = credentials.get("smtp_username")
    password = credentials.get("smtp_password")

    message = EmailMessage()
    message["Subject"] = "OpsPilot update"
    message["From"] = from_address
    message["To"] = recipient
    message.set_content(text)

    with smtplib.SMTP(host, port, timeout=10) as smtp:
        smtp.starttls()
        if username and password:
            smtp.login(username, password)
        smtp.send_message(message)
    return True


_SENDERS = {
    "line": _send_line,
    "telegram": _send_telegram,
    "whatsapp": _send_whatsapp,
    "email": _send_email,
}
