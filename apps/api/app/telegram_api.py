import os


def api_base() -> str:
    """Telegram Bot API root. Overridable so tests and local runs can talk to a fake server."""
    return os.getenv("TELEGRAM_API_BASE", "https://api.telegram.org").rstrip("/")
