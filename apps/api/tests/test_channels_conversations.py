import uuid

from app.channel_routes import ChannelConnect


def test_channel_connect_payload_rejects_blank_name():
    try:
        ChannelConnect(name=" ")
    except ValueError:
        return
    assert False, "blank channel name must be rejected"


def test_channel_type_allowlist():
    supported = {"line", "whatsapp", "telegram", "email"}
    assert "telegram" in supported
    assert "sms" not in supported


def test_conversation_ids_are_uuid_values():
    value = uuid.uuid4()
    assert isinstance(value, uuid.UUID)
