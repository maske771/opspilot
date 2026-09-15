import uuid

import pytest

from app.channel_routes import SUPPORTED_CHANNELS, normalize_channel_name


def test_channel_connect_payload_rejects_blank_name():
    with pytest.raises(ValueError, match="must not be blank"):
        normalize_channel_name("   ")


def test_channel_type_allowlist():
    assert SUPPORTED_CHANNELS == {"line", "whatsapp", "telegram", "email"}
    assert "sms" not in SUPPORTED_CHANNELS


def test_channel_name_is_trimmed():
    assert normalize_channel_name("  Telegram support  ") == "Telegram support"


def test_conversation_ids_are_uuid_values():
    value = uuid.uuid4()
    assert isinstance(value, uuid.UUID)
