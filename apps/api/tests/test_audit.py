import uuid

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app import media
from app.audit import list_audit_events, ticket_history
from app.auth import create_access_token
from app.channel_routes import ChannelUpdate, update_channel
from app.customer_routes import CustomerUpdate, update_customer
from app.db import get_db
from app.main import app
from app.models import Channel, Conversation, Customer, Organization, Property, TicketPriority, User, UserRole
from app.organization_routes import OrgSlaUpdate, update_organization_sla
from app.property_routes import regenerate_property_code
from app.ticket_note_routes import add_note
from app.tickets import (
    TicketAssign,
    TicketCreate,
    TicketUpdate,
    accept_ticket,
    assign_ticket,
    complete_ticket,
    create_ticket,
    start_ticket,
    update_ticket,
)
from app.user_routes import UserRoleUpdate, update_user_role
from app.webhook_service import _open_ticket


@pytest.fixture(autouse=True)
def media_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(media, "MEDIA_ROOT", tmp_path)


def make_user(db, org, role=UserRole.OWNER, specialties=None):
    user = User(organization_id=org.id, email=f"{role.value}-{uuid.uuid4().hex[:6]}@example.com", password_hash="h", role=role, specialties=specialties or [])
    db.add(user)
    db.commit()
    return user


def setup(db):
    org = Organization(name="Org")
    db.add(org)
    db.commit()
    return org, make_user(db, org)


def actions(events):
    return [e.action for e in events]


def test_a_ticket_lifecycle_is_recorded_in_order_with_actors(db_session):
    org, owner = setup(db_session)
    tech = make_user(db_session, org, UserRole.TECHNICIAN, ["plumbing"])

    ticket = create_ticket(TicketCreate(organization_id=org.id, title="Leak", description="Sink", category="plumbing"), user=owner, db=db_session)
    accept_ticket(ticket.id, user=tech, db=db_session)
    start_ticket(ticket.id, user=tech, db=db_session)
    add_note(db_session, tech, ticket.id, "Fixed", [])
    complete_ticket(ticket.id, user=tech, db=db_session)

    history = ticket_history(ticket.id, user=owner, db=db_session)
    assert actions(history) == ["created", "assigned", "status_changed", "status_changed", "note_added", "status_changed"]
    created, auto_assigned, accepted = history[0], history[1], history[2]
    assert created.details == {"source": "manual", "category": "plumbing", "priority": "medium"}
    assert created.actor_email == owner.email
    assert auto_assigned.actor_id is None and auto_assigned.details == {"auto": True, "from": None, "to": str(tech.id)}
    assert accepted.actor_email == tech.email and accepted.details == {"from": "assigned", "to": "accepted"}
    assert history[-1].details == {"from": "in_progress", "to": "completed"}


def test_edits_record_old_and_new_values_but_not_description_text(db_session):
    org, owner = setup(db_session)
    other = make_user(db_session, org, UserRole.STAFF)
    ticket = create_ticket(TicketCreate(organization_id=org.id, title="Leak", description="Sink"), user=owner, db=db_session)

    update_ticket(ticket.id, TicketUpdate(priority=TicketPriority.HIGH, description="Sink and floor", title="Leak"), user=owner, db=db_session)
    assign_ticket(ticket.id, TicketAssign(assignee_id=other.id), user=owner, db=db_session)
    assign_ticket(ticket.id, TicketAssign(assignee_id=other.id), user=owner, db=db_session)  # no-op, not recorded

    history = ticket_history(ticket.id, user=owner, db=db_session)
    assert actions(history) == ["created", "updated", "assigned", "status_changed"]
    assert history[1].details == {"fields": {"priority": {"from": "medium", "to": "high"}, "description": {}}}
    assert history[2].details == {"from": None, "to": str(other.id)}


def test_chat_tickets_are_recorded_without_an_actor(db_session):
    org, owner = setup(db_session)
    channel = Channel(organization_id=org.id, type="telegram", account_id="bot", name="Bot", status="connected")
    customer = Customer(organization_id=org.id, name="Anna")
    db_session.add_all([channel, customer])
    db_session.flush()
    conversation = Conversation(organization_id=org.id, customer_id=customer.id, channel_id=channel.id)
    db_session.add(conversation)
    db_session.flush()

    ticket = _open_ticket(db_session, org.id, customer, conversation, "The toilet is leaking", False)
    db_session.commit()

    [created] = ticket_history(ticket.id, user=owner, db=db_session)
    assert created.actor_id is None and created.details["source"] == "chat"


def test_history_of_another_organizations_ticket_is_not_found(db_session):
    org, owner = setup(db_session)
    _, outsider = setup(db_session)
    ticket = create_ticket(TicketCreate(organization_id=org.id, title="x", description="y"), user=owner, db=db_session)
    with pytest.raises(HTTPException) as exc:
        ticket_history(ticket.id, user=outsider, db=db_session)
    assert exc.value.status_code == 404


def test_sensitive_admin_actions_are_logged_without_secrets(db_session):
    org, owner = setup(db_session)
    staff = make_user(db_session, org, UserRole.STAFF)
    prop = Property(organization_id=org.id, name="Garden Villas")
    customer = Customer(organization_id=org.id, name="Anna")
    channel = Channel(organization_id=org.id, type="telegram", account_id="bot", name="Bot", status="connected", credentials={"bot_token": "old"})
    db_session.add_all([prop, customer, channel])
    db_session.commit()

    update_user_role(staff.id, UserRoleUpdate(role=UserRole.MANAGER), user=owner, db=db_session)
    update_customer(customer.id, CustomerUpdate(property_id=prop.id), user=owner, db=db_session)
    regenerate_property_code(prop.id, user=owner, db=db_session)
    update_channel(channel.id, ChannelUpdate(credentials={"bot_token": "123:SECRET"}), user=owner, db=db_session)
    update_organization_sla(OrgSlaUpdate(high={"response_minutes": 15, "resolution_minutes": 120}), user=owner, db=db_session)

    events = {e.action: e for e in list_audit_events(entity_type=None, entity_id=None, limit=100, offset=0, user=owner, db=db_session)}
    assert set(events) == {"role_changed", "property_changed", "code_regenerated", "updated", "sla_changed"}
    assert events["role_changed"].details == {"email": staff.email, "from": "staff", "to": "manager"}
    assert events["property_changed"].details["property_id"] == {"from": None, "to": str(prop.id)}
    assert prop.code not in str(events["code_regenerated"].details)
    assert events["updated"].details == {"type": "telegram", "name": "Bot", "fields": ["credentials"]}
    assert "SECRET" not in str([e.details for e in events.values()])
    assert events["sla_changed"].details["to"] == {"high": {"response_minutes": 15, "resolution_minutes": 120}}

    users_only = list_audit_events(entity_type="user", entity_id=None, limit=100, offset=0, user=owner, db=db_session)
    assert actions(users_only) == ["role_changed"]


def test_only_owner_and_admin_read_the_organization_log(db_session):
    org, owner = setup(db_session)
    manager = make_user(db_session, org, UserRole.MANAGER)
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        client = TestClient(app)
        as_manager = client.get("/audit-events", headers={"Authorization": f"Bearer {create_access_token(manager)}"})
        as_owner = client.get("/audit-events", headers={"Authorization": f"Bearer {create_access_token(owner)}"})
        assert as_manager.status_code == 403
        assert as_owner.status_code == 200
    finally:
        app.dependency_overrides.clear()
