import io
import logging
import sys
import uuid

import httpx

from app import media, outbound
from app.log_redaction import RedactingFormatter, RedactTokenFilter
from app.models import Channel

BOT_TOKEN = "123456789:AAEabcdefghijklmnopqrstuvwxyz0123456"


def opspilot_handler() -> logging.Handler:
    import app.main  # noqa: F401  (installs the handler)

    return next(h for h in logging.getLogger("opspilot").handlers if isinstance(h.formatter, RedactingFormatter))


def capture_opspilot_logs(monkeypatch) -> io.StringIO:
    handler = opspilot_handler()
    stream = io.StringIO()
    monkeypatch.setattr(handler, "stream", stream)
    return stream


def rejected_by_telegram(url, **kwargs):
    return httpx.Response(401, request=httpx.Request("POST", url))


def render(*args) -> str:
    record = logging.LogRecord("uvicorn.access", logging.INFO, __file__, 1, '%s - "%s %s HTTP/%s" %d', args, None)
    assert RedactTokenFilter().filter(record)
    return record.getMessage()


def test_token_query_parameter_is_masked_in_access_log_lines():
    line = render("1.2.3.4:5", "POST", "/webhooks/telegram/bot?token=SECRETVALUE", "1.1", 200)
    assert "SECRETVALUE" not in line
    assert "/webhooks/telegram/bot?token=***" in line


def test_masks_token_anywhere_in_the_query_and_keeps_other_parameters():
    line = render("1.2.3.4:5", "GET", "/webhooks/whatsapp/a?hub.mode=subscribe&token=SECRETVALUE&x=1", "1.1", 200)
    assert "SECRETVALUE" not in line
    assert "hub.mode=subscribe" in line and "x=1" in line


def test_lines_without_a_token_are_untouched():
    assert render("1.2.3.4:5", "GET", "/tickets?status=new", "1.1", 200) == '1.2.3.4:5 - "GET /tickets?status=new HTTP/1.1" 200'


def test_formatter_masks_bot_tokens_in_messages_and_tracebacks():
    try:
        raise RuntimeError(f"Client error for url 'https://api.telegram.org/bot{BOT_TOKEN}/sendMessage'")
    except RuntimeError:
        record = logging.LogRecord("opspilot.x", logging.ERROR, __file__, 1, "failed for https://api.telegram.org/file/bot%s/a.jpg", (BOT_TOKEN,), sys.exc_info())
    text = RedactingFormatter("%(message)s").format(record)
    assert BOT_TOKEN not in text and "AAEabcdef" not in text
    assert "bot***" in text


def test_a_failed_telegram_send_does_not_leak_the_bot_token(monkeypatch):
    stream = capture_opspilot_logs(monkeypatch)
    monkeypatch.setattr(outbound.httpx, "post", rejected_by_telegram)
    channel = Channel(id=uuid.uuid4(), type="telegram", account_id="a", name="n", credentials={"bot_token": BOT_TOKEN})

    assert outbound.send_message(channel, "42", "hi") is False

    logged = stream.getvalue()
    assert "Failed to send message" in logged
    assert BOT_TOKEN not in logged
    assert "bot***" in logged


def test_a_failed_photo_download_does_not_leak_the_bot_token(monkeypatch):
    stream = capture_opspilot_logs(monkeypatch)
    monkeypatch.setattr(media.httpx, "get", lambda url, **kwargs: rejected_by_telegram(url))

    assert media.download_telegram_photo(BOT_TOKEN, "file123") is None

    logged = stream.getvalue()
    assert "Failed to download Telegram photo" in logged
    assert BOT_TOKEN not in logged
