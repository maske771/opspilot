import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app import webhook_routes
from app.main import app
from app.models import Channel, Organization

TOKEN = "tok-" + uuid.uuid4().hex


@pytest.fixture
def client(db_session, monkeypatch):
    monkeypatch.delenv("WEBHOOK_SECRET", raising=False)
    monkeypatch.setattr(webhook_routes, "SessionLocal", sessionmaker(bind=db_session.get_bind(), expire_on_commit=False))
    return TestClient(app)


def make_channel(db_session, provider="telegram", status="connected"):
    org = Organization(name="Org")
    db_session.add(org)
    db_session.flush()
    account_id = "acc-" + uuid.uuid4().hex[:12]
    db_session.add(Channel(organization_id=org.id, type=provider, account_id=account_id, name="Bot", status=status, webhook_token=TOKEN))
    db_session.commit()
    return account_id


def post(client, provider, account_id, *, params=None, headers=None):
    # A body that isn't JSON: an authorized request gets a 400 from the payload check,
    # which proves it got past authentication without needing the webhook_events table.
    return client.post(f"/webhooks/{provider}/{account_id}", params=params, headers=headers, content=b"not json")


def test_request_without_credentials_is_rejected(client, db_session):
    account_id = make_channel(db_session)
    assert post(client, "telegram", account_id).status_code == 401


def test_wrong_token_is_rejected(client, db_session):
    account_id = make_channel(db_session)
    assert post(client, "telegram", account_id, params={"token": "nope"}).status_code == 401
    assert post(client, "telegram", account_id, headers={"X-Webhook-Token": "nope"}).status_code == 401


def test_unknown_channel_looks_the_same_as_bad_credentials(client):
    assert post(client, "telegram", "does-not-exist", params={"token": TOKEN}).status_code == 401


def test_unsupported_provider_is_not_found(client, db_session):
    account_id = make_channel(db_session)
    assert post(client, "sms", account_id, params={"token": TOKEN}).status_code == 404


def test_token_in_query_is_accepted(client, db_session):
    account_id = make_channel(db_session)
    assert post(client, "telegram", account_id, params={"token": TOKEN}).status_code == 400


def test_telegram_secret_header_is_accepted(client, db_session):
    account_id = make_channel(db_session)
    assert post(client, "telegram", account_id, headers={"X-Telegram-Bot-Api-Secret-Token": TOKEN}).status_code == 400


def test_generic_token_header_is_accepted(client, db_session):
    account_id = make_channel(db_session)
    assert post(client, "telegram", account_id, headers={"X-Webhook-Token": TOKEN}).status_code == 400


def test_token_of_another_channel_is_rejected(client, db_session):
    account_id = make_channel(db_session)
    other = make_channel(db_session)
    db_session.execute(
        Channel.__table__.update().where(Channel.account_id == other).values(webhook_token="different-" + uuid.uuid4().hex)
    )
    db_session.commit()
    assert post(client, "telegram", other, params={"token": TOKEN}).status_code == 401
    assert post(client, "telegram", account_id, params={"token": TOKEN}).status_code == 400


def test_disconnected_channel_is_rejected_even_with_the_right_token(client, db_session):
    account_id = make_channel(db_session, status="disconnected")
    assert post(client, "telegram", account_id, params={"token": TOKEN}).status_code == 401


def test_whatsapp_verification_handshake(client, db_session):
    account_id = make_channel(db_session, provider="whatsapp")
    ok = client.get(
        f"/webhooks/whatsapp/{account_id}",
        params={"hub.mode": "subscribe", "hub.verify_token": TOKEN, "hub.challenge": "12345"},
    )
    assert ok.status_code == 200
    assert ok.text == "12345"

    bad_token = client.get(f"/webhooks/whatsapp/{account_id}", params={"hub.mode": "subscribe", "hub.verify_token": "x", "hub.challenge": "1"})
    bad_mode = client.get(f"/webhooks/whatsapp/{account_id}", params={"hub.mode": "unsubscribe", "hub.verify_token": TOKEN, "hub.challenge": "1"})
    no_challenge = client.get(f"/webhooks/whatsapp/{account_id}", params={"hub.mode": "subscribe", "hub.verify_token": TOKEN})
    assert bad_token.status_code == bad_mode.status_code == no_challenge.status_code == 403
