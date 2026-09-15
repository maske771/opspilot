import uuid

import pytest

from app.channel_routes import SUPPORTED_CHANNELS, normalize_channel_name, normalize_channel_value
from app.webhook_service import normalize_event


def test_channel_connect_payload_rejects_blank_name():
    with pytest.raises(ValueError, match="must not be blank"):
        normalize_channel_name("   ")


def test_channel_account_id_rejects_blank_value():
    with pytest.raises(ValueError, match="must not be blank"):
        normalize_channel_value("   ", "account_id")


def test_channel_type_allowlist():
    assert SUPPORTED_CHANNELS == {"line", "whatsapp", "telegram", "email"}
    assert "sms" not in SUPPORTED_CHANNELS


def test_channel_name_is_trimmed():
    assert normalize_channel_name("  Telegram support  ") == "Telegram support"


def test_conversation_ids_are_uuid_values():
    value = uuid.uuid4()
    assert isinstance(value, uuid.UUID)


def test_normalize_telegram_message():
    event = normalize_event("telegram", {"message": {"message_id": 17, "text": "Water leak", "chat": {"id": 100}, "from": {"id": 200, "first_name": "Ivan"}}})
    assert event is not None
    assert event.external_conversation_id == "100"
    assert event.external_user_id == "200"
    assert event.external_message_id == "17"
    assert event.text == "Water leak"
    assert event.customer_name == "Ivan"


def test_normalize_line_message():
    event = normalize_event("line", {"events": [{"source": {"userId": "U123"}, "message": {"id": "M1", "text": "Hello"}}]})
    assert event is not None
    assert event.external_conversation_id == "U123"
    assert event.external_user_id == "U123"
    assert event.external_message_id == "M1"
    assert event.text == "Hello"


def test_unknown_payload_is_stored_but_not_normalized():
    assert normalize_event("telegram", {"update_id": 1}) is None
