import uuid
from unittest.mock import MagicMock, patch

from app.models import Channel
from app.outbound import send_message


def make_channel(channel_type: str, credentials: dict | None) -> Channel:
    return Channel(id=uuid.uuid4(), type=channel_type, credentials=credentials)


def test_send_message_without_credentials_is_skipped():
    channel = make_channel("telegram", None)
    assert send_message(channel, "chat-1", "hello") is False


def test_send_message_unknown_channel_type_is_skipped():
    channel = make_channel("carrier_pigeon", {"anything": "here"})
    assert send_message(channel, "recipient", "hello") is False


@patch("app.outbound.httpx.post")
def test_send_message_telegram_dispatches_correctly(mock_post):
    mock_post.return_value = MagicMock(raise_for_status=lambda: None)
    channel = make_channel("telegram", {"bot_token": "abc123"})

    assert send_message(channel, "chat-1", "hello") is True
    mock_post.assert_called_once()
    url = mock_post.call_args.args[0]
    assert url == "https://api.telegram.org/botabc123/sendMessage"
    assert mock_post.call_args.kwargs["json"] == {"chat_id": "chat-1", "text": "hello"}


@patch("app.outbound.httpx.post")
def test_send_message_line_dispatches_correctly(mock_post):
    mock_post.return_value = MagicMock(raise_for_status=lambda: None)
    channel = make_channel("line", {"channel_access_token": "token-1"})

    assert send_message(channel, "user-1", "hello") is True
    kwargs = mock_post.call_args.kwargs
    assert kwargs["headers"]["Authorization"] == "Bearer token-1"
    assert kwargs["json"]["to"] == "user-1"


@patch("app.outbound.httpx.post")
def test_send_message_whatsapp_missing_credentials_is_skipped(mock_post):
    channel = make_channel("whatsapp", {"access_token": "token-1"})  # missing phone_number_id

    assert send_message(channel, "+1234567890", "hello") is False
    mock_post.assert_not_called()


@patch("app.outbound.httpx.post")
def test_send_message_provider_error_does_not_raise(mock_post):
    mock_post.side_effect = RuntimeError("network down")
    channel = make_channel("telegram", {"bot_token": "abc123"})

    assert send_message(channel, "chat-1", "hello") is False


@patch("app.outbound.smtplib.SMTP")
def test_send_message_email_dispatches_correctly(mock_smtp_cls):
    mock_smtp = MagicMock()
    mock_smtp_cls.return_value.__enter__.return_value = mock_smtp
    channel = make_channel(
        "email",
        {"smtp_host": "smtp.example.com", "from_address": "ops@example.com", "smtp_username": "u", "smtp_password": "p"},
    )

    assert send_message(channel, "guest@example.com", "hello") is True
    mock_smtp.login.assert_called_once_with("u", "p")
    mock_smtp.send_message.assert_called_once()
