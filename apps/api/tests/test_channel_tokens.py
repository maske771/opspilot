import pytest
from fastapi import HTTPException

from app import channel_routes
from app.channel_routes import ChannelConnect, connect_channel, register_webhook, rotate_webhook_token, visible_channel
from app.models import Channel, Organization, User, UserRole


@pytest.fixture
def registered(monkeypatch):
    calls = []
    monkeypatch.setattr(channel_routes, "register_telegram_webhook", lambda channel: calls.append(channel.id) or True)
    return calls


def make_user(db_session, role: UserRole, org: Organization | None = None) -> User:
    if org is None:
        org = Organization(name="Org")
        db_session.add(org)
        db_session.flush()
    user = User(organization_id=org.id, email=f"{role.value}-{org.id}@example.com", password_hash="hash", role=role)
    db_session.add(user)
    db_session.commit()
    return user


def test_connect_issues_a_fresh_random_token_per_channel(db_session, registered):
    owner = make_user(db_session, UserRole.OWNER)
    first = connect_channel("telegram", ChannelConnect(account_id="a1", name="One", credentials={"bot_token": "x"}), user=owner, db=db_session)
    second = connect_channel("line", ChannelConnect(account_id="a2", name="Two"), user=owner, db=db_session)

    assert len(first.webhook_token) >= 32
    assert first.webhook_token != second.webhook_token
    assert registered == [first.id]


def test_only_owner_and_admin_can_see_the_token(db_session, registered):
    owner = make_user(db_session, UserRole.OWNER)
    channel = connect_channel("line", ChannelConnect(account_id="a1", name="One"), user=owner, db=db_session)

    org = db_session.get(Organization, owner.organization_id)
    assert visible_channel(channel, owner).webhook_token == channel.webhook_token
    assert visible_channel(channel, make_user(db_session, UserRole.ADMIN, org)).webhook_token == channel.webhook_token
    for role in (UserRole.MANAGER, UserRole.STAFF, UserRole.TECHNICIAN):
        assert visible_channel(channel, make_user(db_session, role, org)).webhook_token is None


def test_rotating_replaces_the_token_and_repoints_telegram(db_session, registered):
    owner = make_user(db_session, UserRole.OWNER)
    channel = connect_channel("telegram", ChannelConnect(account_id="a1", name="One", credentials={"bot_token": "x"}), user=owner, db=db_session)
    old = channel.webhook_token
    registered.clear()

    rotated = rotate_webhook_token(channel.id, user=owner, db=db_session)

    assert rotated.webhook_token != old
    assert db_session.get(Channel, channel.id).webhook_token == rotated.webhook_token
    assert registered == [channel.id]


def test_rotating_is_scoped_to_the_callers_organization(db_session, registered):
    owner = make_user(db_session, UserRole.OWNER)
    stranger = make_user(db_session, UserRole.OWNER)
    channel = connect_channel("line", ChannelConnect(account_id="a1", name="One"), user=owner, db=db_session)

    with pytest.raises(HTTPException) as exc:
        rotate_webhook_token(channel.id, user=stranger, db=db_session)
    assert exc.value.status_code == 404


def test_register_webhook_rejects_non_telegram_channels(db_session, registered):
    owner = make_user(db_session, UserRole.OWNER)
    channel = connect_channel("line", ChannelConnect(account_id="a1", name="One"), user=owner, db=db_session)

    with pytest.raises(HTTPException) as exc:
        register_webhook(channel.id, user=owner, db=db_session)
    assert exc.value.status_code == 400
