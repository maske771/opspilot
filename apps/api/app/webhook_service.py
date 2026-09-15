from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Conversation, Customer, CustomerIdentity, Message, Ticket, TicketPriority, TicketStatus
from .sla import calculate_sla


@dataclass(frozen=True)
class NormalizedEvent:
    external_conversation_id: str
    external_user_id: str
    external_message_id: str | None
    text: str
    customer_name: str | None = None
    phone: str | None = None
    email: str | None = None


def _first(mapping: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = mapping.get(key)
        if value is not None:
            return value
    return None


def normalize_event(provider: str, payload: dict[str, Any]) -> NormalizedEvent | None:
    provider = provider.lower()
    if provider == "line":
        event = (payload.get("events") or [{}])[0]
        source = event.get("source") or {}
        message = event.get("message") or {}
        user_id = _first(source, "userId", "user_id")
        conversation_id = _first(source, "groupId", "roomId", "userId", "group_id", "room_id", "user_id")
        message_id = _first(message, "id", "messageId", "message_id")
        text = _first(message, "text", "body")
        if user_id and conversation_id and text:
            return NormalizedEvent(str(conversation_id), str(user_id), str(message_id) if message_id else None, str(text))
        return None

    if provider == "telegram":
        message = payload.get("message") or payload.get("edited_message") or {}
        chat = message.get("chat") or {}
        sender = message.get("from") or {}
        user_id = _first(sender, "id")
        conversation_id = _first(chat, "id")
        message_id = _first(message, "message_id", "id")
        text = _first(message, "text", "caption")
        name = " ".join(filter(None, [_first(sender, "first_name"), _first(sender, "last_name")])) or None
        if user_id and conversation_id and text:
            return NormalizedEvent(str(conversation_id), str(user_id), str(message_id) if message_id else None, str(text), customer_name=name)
        return None

    if provider == "whatsapp":
        try:
            value = payload["entry"][0]["changes"][0]["value"]
            message = (value.get("messages") or [{}])[0]
            contact = (value.get("contacts") or [{}])[0]
            user_id = _first(message, "from") or _first(contact, "wa_id")
            conversation_id = _first(message, "from") or _first(contact, "wa_id")
            message_id = _first(message, "id", "message_id")
            text_obj = message.get("text") or {}
            text = _first(text_obj, "body") or _first(message, "text", "body")
            profile = contact.get("profile") or {}
            name = _first(profile, "name")
            if user_id and conversation_id and text:
                return NormalizedEvent(str(conversation_id), str(user_id), str(message_id) if message_id else None, str(text), customer_name=name, phone=str(user_id))
        except (KeyError, IndexError, TypeError):
            pass
        return None

    if provider == "email":
        sender = payload.get("from") or payload.get("sender") or {}
        if isinstance(sender, dict):
            email = _first(sender, "email", "address")
            name = _first(sender, "name")
        else:
            email, name = str(sender), None
        conversation_id = _first(payload, "conversation_id", "thread_id", "threadId") or email
        message_id = _first(payload, "message_id", "messageId", "id")
        text = _first(payload, "text", "body")
        if email and conversation_id and text:
            return NormalizedEvent(str(conversation_id), str(email), str(message_id) if message_id else None, str(text), customer_name=name, email=str(email))
        return None

    return None


def ingest_normalized_event(db: Session, organization_id, channel, event: NormalizedEvent) -> tuple[dict[str, Any], bool, bool]:
    identity = db.scalar(select(CustomerIdentity).where(CustomerIdentity.organization_id == organization_id, CustomerIdentity.channel_type == channel.type, CustomerIdentity.external_user_id == event.external_user_id))
    if identity:
        customer = db.get(Customer, identity.customer_id)
    else:
        customer = Customer(organization_id=organization_id, name=event.customer_name, phone=event.phone, email=event.email)
        db.add(customer)
        db.flush()
        identity = CustomerIdentity(organization_id=organization_id, customer_id=customer.id, channel_type=channel.type, external_user_id=event.external_user_id)
        db.add(identity)
        db.flush()

    conversation = db.scalar(select(Conversation).where(Conversation.organization_id == organization_id, Conversation.channel_id == channel.id, Conversation.external_conversation_id == event.external_conversation_id))
    if conversation is None:
        conversation = Conversation(organization_id=organization_id, customer_id=customer.id, channel_id=channel.id, external_conversation_id=event.external_conversation_id, status="open")
        db.add(conversation)
        db.flush()
    elif conversation.customer_id is None:
        conversation.customer_id = customer.id

    message = None
    if event.external_message_id:
        message = db.scalar(select(Message).where(Message.conversation_id == conversation.id, Message.external_message_id == event.external_message_id))
    message_created = message is None
    if message_created:
        message = Message(conversation_id=conversation.id, direction="inbound", content=event.text, external_message_id=event.external_message_id)
        db.add(message)
        db.flush()

    ticket = db.scalar(select(Ticket).where(Ticket.organization_id == organization_id, Ticket.conversation_id == conversation.id, Ticket.status != TicketStatus.CLOSED).order_by(Ticket.created_at.desc()))
    ticket_created = ticket is None
    if ticket_created:
        ticket = Ticket(organization_id=organization_id, customer_id=customer.id, conversation_id=conversation.id, title=event.text[:255], description=event.text, category="other", priority=TicketPriority.MEDIUM, status=TicketStatus.NEW)
        db.add(ticket)
        db.flush()
        ticket.response_deadline, ticket.resolution_deadline = calculate_sla(ticket.priority, ticket.created_at)

    return {"customer_id": customer.id, "conversation_id": conversation.id, "message_id": message.id, "ticket_id": ticket.id}, message_created, ticket_created
