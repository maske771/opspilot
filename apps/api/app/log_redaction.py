import logging
import re

_TOKEN_PARAM = re.compile(r"([?&]token=)[^&\s\"]+")
# Telegram embeds the bot token in the URL path: /bot<id>:<secret>/method and /file/bot<id>:<secret>/...
_BOT_TOKEN = re.compile(r"(bot)\d{5,}:[A-Za-z0-9_-]{20,}")


def redact(text: str) -> str:
    return _BOT_TOKEN.sub(r"\1***", _TOKEN_PARAM.sub(r"\1***", text))


class RedactTokenFilter(logging.Filter):
    """Webhook URLs carry a secret `?token=`; keep it out of access logs."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.args, tuple):
            record.args = tuple(redact(arg) if isinstance(arg, str) else arg for arg in record.args)
        if isinstance(record.msg, str):
            record.msg = redact(record.msg)
        return True


class RedactingFormatter(logging.Formatter):
    """Scrubs secrets from the fully rendered record, tracebacks included: httpx errors embed the
    request URL, and for Telegram that URL contains the bot token."""

    def format(self, record: logging.LogRecord) -> str:
        return redact(super().format(record))
