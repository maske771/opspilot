import logging
import os
import uuid
from pathlib import Path

import httpx

logger = logging.getLogger("opspilot.media")

MEDIA_ROOT = Path(os.getenv("MEDIA_ROOT", "/media"))


def save_bytes(organization_id: uuid.UUID, content: bytes, extension: str = ".jpg") -> str:
    org_dir = MEDIA_ROOT / str(organization_id)
    org_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid.uuid4()}{extension}"
    (org_dir / filename).write_bytes(content)
    return f"{organization_id}/{filename}"


def read_bytes(storage_path: str) -> bytes:
    return (MEDIA_ROOT / storage_path).read_bytes()


def download_telegram_photo(bot_token: str, file_id: str) -> bytes | None:
    """Fetch a Telegram photo's bytes via getFile + the file download endpoint. Telegram always
    re-encodes uploaded photos as JPEG, so the content type is fixed."""
    try:
        info = httpx.get(f"https://api.telegram.org/bot{bot_token}/getFile", params={"file_id": file_id}, timeout=10)
        info.raise_for_status()
        file_path = info.json()["result"]["file_path"]
        content = httpx.get(f"https://api.telegram.org/file/bot{bot_token}/{file_path}", timeout=20)
        content.raise_for_status()
        return content.content
    except Exception:
        logger.exception("Failed to download Telegram photo (file_id=%s)", file_id)
        return None
