from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from .ai_intake import classify, is_actionable_request
from .ai_response import detect_language, generate_greeting, get_response_generator, registration_text
from .assignment import find_assignee_for_category
from .customer_match import find_customer, normalize_email, normalize_phone
from .models import Conversation, Customer, CustomerIdentity, Message, MessageAttachment, Property, Ticket, TicketStatus, normalize_property_code
from .services import intake_rules, sla_overrides_for
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
    media_file_id: str | None = None
    media_type: str | None = None

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
        source, message = event.get("source") or {}, event.get("message") or {}
        user_id = _first(source, "userId", "user_id")
        conversation_id = _first(source, "groupId", "roomId", "userId", "group_id", "room_id", "user_id")
        message_id, text = _first(message, "id", "messageId", "message_id"), _first(message, "text", "body")
        if user_id and conversation_id and text:
            return NormalizedEvent(str(conversation_id), str(user_id), str(message_id) if message_id else None, str(text))
        return None
    if provider == "telegram":
        message = payload.get("message") or payload.get("edited_message") or {}
        chat, sender = message.get("chat") or {}, message.get("from") or {}
        user_id, conversation_id = _first(sender, "id"), _first(chat, "id")
        message_id, text = _first(message, "message_id", "id"), _first(message, "text", "caption") or ""
        name = " ".join(filter(None, [_first(sender, "first_name"), _first(sender, "last_name")])) or None
        photo_sizes = message.get("photo")
        media_file_id = photo_sizes[-1]["file_id"] if photo_sizes else None
        if text.strip().startswith("/"):
            return None
        if user_id and conversation_id and (text or media_file_id):
            return NormalizedEvent(
                str(conversation_id), str(user_id), str(message_id) if message_id else None, str(text),
                customer_name=name, media_file_id=media_file_id, media_type="photo" if media_file_id else None,
            )
        return None
    if provider == "whatsapp":
        try:
            value = payload["entry"][0]["changes"][0]["value"]
            message, contact = (value.get("messages") or [{}])[0], (value.get("contacts") or [{}])[0]
            user_id = _first(message, "from") or _first(contact, "wa_id")
            message_id = _first(message, "id", "message_id")
            text_obj = message.get("text") or {}
            text = _first(text_obj, "body") or _first(message, "text", "body")
            name = _first(contact.get("profile") or {}, "name")
            if user_id and text:
                return NormalizedEvent(str(user_id), str(user_id), str(message_id) if message_id else None, str(text), customer_name=name, phone=str(user_id))
        except (KeyError, IndexError, TypeError):
            pass
        return None
    if provider == "email":
        sender = payload.get("from") or payload.get("sender") or {}
        if isinstance(sender, dict):
            email, name = _first(sender, "email", "address"), _first(sender, "name")
        else:
            email, name = str(sender), None
        conversation_id = _first(payload, "conversation_id", "thread_id", "threadId") or email
        message_id, text = _first(payload, "message_id", "messageId", "id"), _first(payload, "text", "body")
        if email and conversation_id and text:
            return NormalizedEvent(str(conversation_id), str(email), str(message_id) if message_id else None, str(text), customer_name=name, email=str(email))
    return None

def ingest_normalized_event(db: Session, organization_id, channel, event: NormalizedEvent) -> tuple[dict[str, Any], bool, bool]:
    channel_type, channel_id = channel["type"], channel["id"]
    match = find_customer(
        db,
        organization_id,
        channel_type=channel_type,
        external_user_id=event.external_user_id,
        email=event.email,
        phone=event.phone,
    )
    customer = match.customer
    if customer is None:
        customer = Customer(
            organization_id=organization_id,
            name=event.customer_name,
            phone=normalize_phone(event.phone),
            email=normalize_email(event.email),
        )
        db.add(customer)
        db.flush()
    else:
        if not customer.name and event.customer_name:
            customer.name = event.customer_name
        if not customer.email and event.email:
            customer.email = normalize_email(event.email)
        if not customer.phone and event.phone:
            customer.phone = normalize_phone(event.phone)

    identity = db.scalar(
        select(CustomerIdentity).where(
            CustomerIdentity.organization_id == organization_id,
            CustomerIdentity.channel_type == channel_type,
            CustomerIdentity.external_user_id == event.external_user_id,
        )
    )
    if identity is None:
        db.add(CustomerIdentity(
            organization_id=organization_id,
            customer_id=customer.id,
            channel_type=channel_type,
            external_user_id=event.external_user_id,
        ))
        db.flush()

    conversation = db.scalar(select(Conversation).where(Conversation.organization_id == organization_id, Conversation.channel_id == channel_id, Conversation.external_conversation_id == event.external_conversation_id))
    if conversation is None:
        conversation = Conversation(organization_id=organization_id, customer_id=customer.id, channel_id=channel_id, external_conversation_id=event.external_conversation_id, status="open")
        db.add(conversation); db.flush()
    elif conversation.customer_id is None:
        conversation.customer_id = customer.id
    message = None
    if event.external_message_id:
        message = db.scalar(select(Message).where(Message.conversation_id == conversation.id, Message.external_message_id == event.external_message_id))
    message_created = message is None
    if message is None:
        message = Message(conversation_id=conversation.id, direction="inbound", content=event.text, external_message_id=event.external_message_id)
        db.add(message); db.flush()
    has_media = event.media_file_id is not None

    ticket = db.scalar(select(Ticket).where(Ticket.organization_id == organization_id, Ticket.conversation_id == conversation.id, Ticket.status != TicketStatus.CLOSED).order_by(Ticket.created_at.desc()))
    ticket_created = False
    reply_text = None

    if message_created:
        language = _conversation_language(db, conversation, event.text)
        generator = get_response_generator()

        # A manager linked the customer in the UI while the bot was still waiting for a code.
        if conversation.pending_step and customer.property_id is not None:
            pending = _take_pending_message(db, conversation)
            if pending is not None and ticket is None:
                ticket = _open_ticket(db, organization_id, customer, conversation, pending.content, _message_has_media(pending))
                ticket_created = True

        needs_property = ticket is None and customer.property_id is None and _org_has_properties(db, organization_id)
        if conversation.pending_step == PROPERTY_CODE_STEP or needs_property:
            reply_text, ticket = _registration_step(db, organization_id, customer, conversation, message, event, has_media, language, generator)
            ticket_created = ticket_created or ticket is not None
        else:
            rules, _ = intake_rules(db, organization_id, customer.property_id)
            if ticket is None and (has_media or is_actionable_request(event.text, rules)):
                ticket = _open_ticket(db, organization_id, customer, conversation, event.text, has_media)
                ticket_created = True
                result = generator.generate(customer_message=event.text, category=ticket.category, priority=ticket.priority.value, language=language, has_media=has_media)
            elif ticket is None:
                result = generate_greeting(customer_message=event.text, language=language)
            else:
                # Don't keep asking for a photo if one already arrived for this ticket.
                photo_on_file = has_media or db.scalar(
                    select(MessageAttachment.id)
                    .join(Message, MessageAttachment.message_id == Message.id)
                    .where(Message.conversation_id == conversation.id, Message.created_at >= ticket.created_at)
                    .limit(1)
                ) is not None
                result = generator.generate_follow_up(
                    customer_message=event.text, ticket_status=ticket.status.value, language=language, category=ticket.category, has_media=photo_on_file
                )
            reply_text = result.text

        db.add(Message(conversation_id=conversation.id, direction="outbound", content=reply_text))
        db.flush()

    data = {"customer_id": customer.id, "conversation_id": conversation.id, "message_id": message.id, "ticket_id": ticket.id if ticket else None, "reply_text": reply_text}
    return data, message_created, ticket_created


PROPERTY_CODE_STEP = "property_code"


def _org_has_properties(db: Session, organization_id) -> bool:
    return db.scalar(select(Property.id).where(Property.organization_id == organization_id).limit(1)) is not None


def _conversation_language(db: Session, conversation: Conversation, text: str):
    """A property code like "K7PX2M" has no language of its own, so fall back to the customer's
    earlier messages in this conversation."""
    if detect_language(text) == "ru":
        return "ru"
    earlier = db.scalars(select(Message.content).where(Message.conversation_id == conversation.id, Message.direction == "inbound"))
    return "ru" if any(detect_language(content or "") == "ru" for content in earlier) else "en"


def _message_has_media(message: Message) -> bool:
    # Attachments are downloaded after ingestion, so a photo-only message may only show up as empty text.
    return bool(message.attachments) or not (message.content or "").strip()


def _take_pending_message(db: Session, conversation: Conversation) -> Message | None:
    pending = db.get(Message, conversation.pending_message_id) if conversation.pending_message_id else None
    conversation.pending_step = None
    conversation.pending_message_id = None
    return pending


def _looks_like_code(text: str) -> bool:
    stripped = text.strip()
    return 4 <= len(normalize_property_code(stripped)) <= 12 and len(stripped.split()) == 1


def _registration_step(db, organization_id, customer, conversation, message, event, has_media, language, generator) -> tuple[str, Ticket | None]:
    """The customer isn't linked to a property yet: ask for the property code, remember their first
    request, and once a valid code arrives link them and turn that request into a ticket."""
    rules, _ = intake_rules(db, organization_id)
    actionable = has_media or is_actionable_request(event.text, rules)

    if conversation.pending_step != PROPERTY_CODE_STEP:
        conversation.pending_step = PROPERTY_CODE_STEP
        conversation.pending_message_id = message.id if actionable else None
        return registration_text("ask_code", language), None

    code = normalize_property_code(event.text)
    prop = db.scalar(select(Property).where(Property.organization_id == organization_id, Property.code == code)) if code else None
    if prop is None:
        if conversation.pending_message_id is None and actionable and not _looks_like_code(event.text):
            conversation.pending_message_id = message.id
        kind = "code_not_found" if _looks_like_code(event.text) else "ask_code"
        return registration_text(kind, language), None

    customer.property_id = prop.id
    pending = _take_pending_message(db, conversation)
    if pending is None:
        return registration_text("linked_how_can_we_help", language, property=prop.name), None

    pending_media = _message_has_media(pending)
    ticket = _open_ticket(db, organization_id, customer, conversation, pending.content, pending_media)
    ack = generator.generate(customer_message=pending.content, category=ticket.category, priority=ticket.priority.value, language=language, has_media=pending_media)
    return f"{registration_text('linked', language, property=prop.name)}\n\n{ack.text}", ticket


def _open_ticket(db: Session, organization_id, customer: Customer, conversation: Conversation, text: str, has_media: bool) -> Ticket:
    rules, fallback_priority = intake_rules(db, organization_id, customer.property_id)
    intake = classify(text or "photo", rules, fallback_priority)
    title = (text.strip() or ("Photo from customer" if has_media else ""))[:255]
    ticket = Ticket(
        organization_id=organization_id,
        customer_id=customer.id,
        conversation_id=conversation.id,
        property_id=customer.property_id,
        unit_id=customer.unit_id,
        title=title,
        description=text.strip() or "Customer sent a photo.",
        category=intake.category,
        priority=intake.priority,
        status=TicketStatus.NEW,
    )
    db.add(ticket)
    db.flush()
    overrides = sla_overrides_for(db, organization_id, ticket.property_id, ticket.category)
    ticket.response_deadline, ticket.resolution_deadline = calculate_sla(ticket.priority, ticket.created_at, overrides)
    assignee = find_assignee_for_category(db, organization_id, ticket.category)
    if assignee is not None:
        ticket.assignee_id = assignee.id
        ticket.status = TicketStatus.ASSIGNED
    return ticket
