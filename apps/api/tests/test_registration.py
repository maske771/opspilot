import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.customer_routes import CustomerUpdate, update_customer
from app.models import Channel, Conversation, Customer, Organization, Property, Service, Ticket, TicketPriority, Unit, User, UserRole
from app.organization_routes import SlaPair
from app.property_routes import regenerate_property_code
from app.property_service_routes import PropertyServiceEntry, PropertyServicesUpdate, update_property_services
from app.services import ensure_services
from app.webhook_service import NormalizedEvent, ingest_normalized_event


def setup(db_session, with_property=True):
    org = Organization(name="Org")
    db_session.add(org)
    db_session.flush()
    owner = User(organization_id=org.id, email=f"owner-{uuid.uuid4().hex[:6]}@example.com", password_hash="h", role=UserRole.OWNER)
    channel = Channel(organization_id=org.id, type="telegram", account_id="bot-" + uuid.uuid4().hex[:6], name="Bot", status="connected")
    db_session.add_all([owner, channel])
    prop = None
    if with_property:
        prop = Property(organization_id=org.id, name="Sunset Tower", code="K7PX2M")
        db_session.add(prop)
    db_session.commit()
    return org, owner, channel, prop


class Chat:
    def __init__(self, db_session, org, channel, user_id="555"):
        self.db, self.org, self.channel, self.user_id, self.n = db_session, org, channel, user_id, 0

    def send(self, text, media=False):
        self.n += 1
        event = NormalizedEvent(
            external_conversation_id=self.user_id, external_user_id=self.user_id, external_message_id=f"{self.user_id}-{self.n}",
            text=text, media_file_id="file" if media else None, media_type="photo" if media else None,
        )
        data, _, ticket_created = ingest_normalized_event(self.db, self.org.id, {"type": self.channel.type, "id": self.channel.id}, event)
        ticket = self.db.get(Ticket, data["ticket_id"]) if data["ticket_id"] else None
        return data["reply_text"], ticket, ticket_created

    @property
    def customer(self):
        conversation = self.db.scalar(select(Conversation).where(Conversation.external_conversation_id == self.user_id, Conversation.channel_id == self.channel.id))
        return self.db.get(Customer, conversation.customer_id)


def test_without_properties_the_bot_opens_a_ticket_right_away(db_session):
    org, _, channel, _ = setup(db_session, with_property=False)

    reply, ticket, created = Chat(db_session, org, channel).send("течёт кран на кухне")

    assert created and ticket.category == "plumbing"
    assert "код" not in reply.lower()


def test_first_request_waits_for_the_code_and_becomes_a_ticket_once_linked(db_session):
    org, _, channel, prop = setup(db_session)
    chat = Chat(db_session, org, channel)

    reply, ticket, created = chat.send("течёт кран на кухне")
    assert not created and ticket is None
    assert "код объекта" in reply

    reply, ticket, created = chat.send("ZZZZZZ")
    assert not created
    assert "Не нашли" in reply

    reply, ticket, created = chat.send("k7p-x2m")  # case and separators don't matter
    assert created
    assert "Sunset Tower" in reply and reply.startswith("Спасибо")  # Russian, from the earlier message
    assert ticket.title == "течёт кран на кухне" and ticket.category == "plumbing"
    assert ticket.property_id == prop.id
    assert chat.customer.property_id == prop.id


def test_a_greeting_first_then_code_then_request(db_session):
    org, _, channel, prop = setup(db_session)
    chat = Chat(db_session, org, channel)

    assert "code" in chat.send("hello")[0].lower()
    reply, ticket, created = chat.send("K7PX2M")
    assert not created and "How can we help" in reply

    reply, ticket, created = chat.send("the light switch is sparking")
    assert created and ticket.category == "electrical" and ticket.property_id == prop.id


def test_a_problem_sent_after_the_question_is_kept_and_the_bot_asks_again(db_session):
    org, _, channel, _ = setup(db_session)
    chat = Chat(db_session, org, channel)

    chat.send("привет")
    reply, _, _ = chat.send("у меня не работает розетка в спальне")
    assert "код объекта" in reply and "Не нашли" not in reply

    _, ticket, created = chat.send("K7PX2M")
    assert created and ticket.title == "у меня не работает розетка в спальне"


def test_a_photo_only_first_message_becomes_a_ticket_after_linking(db_session):
    org, _, channel, _ = setup(db_session)
    chat = Chat(db_session, org, channel)

    chat.send("", media=True)
    reply, ticket, created = chat.send("K7PX2M")

    assert created and ticket.title == "Photo from customer"
    assert "photo" not in reply.split("\n\n", 1)[1].lower()  # no "please send a photo" after a photo


def test_linked_customers_are_classified_within_their_property_services(db_session):
    org, owner, channel, prop = setup(db_session)
    ensure_services(db_session, org.id)
    services = {s.code: s for s in db_session.scalars(select(Service).where(Service.organization_id == org.id))}
    update_property_services(
        prop.id,
        PropertyServicesUpdate(
            services=[PropertyServiceEntry(service_id=services["electrical"].id, sla={TicketPriority.HIGH: SlaPair(response_minutes=5, resolution_minutes=60)})]
        ),
        user=owner,
        db=db_session,
    )
    chat = Chat(db_session, org, channel)
    chat.send("hi")
    chat.send("K7PX2M")

    _, ticket, _ = chat.send("water is leaking from the ceiling")
    assert ticket.category == "other"  # plumbing isn't offered at this property

    chat2 = Chat(db_session, org, channel, user_id="556")
    chat2.send("hi")
    chat2.send("K7PX2M")
    _, ticket, _ = chat2.send("the socket is sparking")
    assert ticket.category == "electrical"
    assert round((ticket.response_deadline - ticket.created_at).total_seconds() / 60) == 5  # property SLA


def test_a_manager_linking_the_customer_in_the_ui_unblocks_the_dialog(db_session):
    org, owner, channel, prop = setup(db_session)
    chat = Chat(db_session, org, channel)
    chat.send("течёт кран")
    update_customer(chat.customer.id, CustomerUpdate(property_id=prop.id), user=owner, db=db_session)

    reply, ticket, created = chat.send("вода уже на полу")

    assert created and ticket.title == "течёт кран" and ticket.property_id == prop.id
    assert "код" not in reply.lower()


def test_existing_customers_with_an_open_ticket_are_not_asked_for_a_code(db_session):
    org, _, channel, _ = setup(db_session, with_property=False)
    chat = Chat(db_session, org, channel)
    chat.send("течёт кран")  # ticket opened before the org had any properties
    db_session.add(Property(organization_id=org.id, name="New", code="NEW234"))
    db_session.commit()

    reply, _, created = chat.send("вода уже на полу")

    assert not created and "код" not in reply.lower()


# ---- manager side


def test_only_managers_and_up_can_change_a_customers_property(db_session):
    org, owner, channel, prop = setup(db_session)
    staff = User(organization_id=org.id, email="s@example.com", password_hash="h", role=UserRole.STAFF)
    customer = Customer(organization_id=org.id, name="Guest")
    db_session.add_all([staff, customer])
    db_session.commit()

    with pytest.raises(HTTPException) as exc:
        update_customer(customer.id, CustomerUpdate(property_id=prop.id), user=staff, db=db_session)
    assert exc.value.status_code == 403
    assert update_customer(customer.id, CustomerUpdate(name="Renamed"), user=staff, db=db_session).name == "Renamed"


def test_unit_must_belong_to_the_property_and_resets_when_property_changes(db_session):
    org, owner, _, prop = setup(db_session)
    other = Property(organization_id=org.id, name="Riverside", code="RIV234")
    db_session.add(other)
    db_session.flush()
    unit = Unit(organization_id=org.id, property_id=prop.id, unit_number="101")
    customer = Customer(organization_id=org.id, name="Guest")
    db_session.add_all([unit, customer])
    db_session.commit()

    with pytest.raises(HTTPException):
        update_customer(customer.id, CustomerUpdate(property_id=other.id, unit_id=unit.id), user=owner, db=db_session)

    linked = update_customer(customer.id, CustomerUpdate(property_id=prop.id, unit_id=unit.id), user=owner, db=db_session)
    assert linked.unit_id == unit.id
    moved = update_customer(customer.id, CustomerUpdate(property_id=other.id), user=owner, db=db_session)
    assert moved.property_id == other.id and moved.unit_id is None


def test_regenerating_a_code_invalidates_the_old_one(db_session):
    org, owner, channel, prop = setup(db_session)

    new_code = regenerate_property_code(prop.id, user=owner, db=db_session).code
    assert new_code != "K7PX2M" and len(new_code) == 6

    chat = Chat(db_session, org, channel)
    chat.send("hi")
    assert "couldn't find" in chat.send("K7PX2M")[0]
    assert "registered" in chat.send(new_code)[0]
