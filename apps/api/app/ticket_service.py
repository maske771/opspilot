import uuid
from datetime import datetime

from .models import Ticket, TicketPriority, TicketStatus
from .sla import calculate_sla


class TicketStateError(ValueError):
    pass


ALLOWED_TRANSITIONS: dict[TicketStatus, set[TicketStatus]] = {
    TicketStatus.NEW: {TicketStatus.ASSIGNED},
    TicketStatus.ASSIGNED: {TicketStatus.ACCEPTED},
    TicketStatus.ACCEPTED: {TicketStatus.IN_PROGRESS},
    TicketStatus.IN_PROGRESS: {TicketStatus.COMPLETED},
    TicketStatus.COMPLETED: {TicketStatus.WAITING_APPROVAL, TicketStatus.CLOSED},
    TicketStatus.WAITING_APPROVAL: {TicketStatus.CLOSED},
    TicketStatus.CLOSED: set(),
}


def transition_ticket(ticket: Ticket, new_status: TicketStatus) -> Ticket:
    if new_status not in ALLOWED_TRANSITIONS[ticket.status]:
        raise TicketStateError(f"Cannot transition ticket from {ticket.status.value} to {new_status.value}")
    ticket.status = new_status
    return ticket


def assign_ticket(ticket: Ticket, assignee_id: uuid.UUID) -> Ticket:
    if ticket.status not in {TicketStatus.NEW, TicketStatus.ASSIGNED}:
        raise TicketStateError("Only new or assigned tickets can be assigned")
    ticket.assignee_id = assignee_id
    ticket.status = TicketStatus.ASSIGNED
    return ticket


def refresh_sla(ticket: Ticket) -> Ticket:
    response_deadline, resolution_deadline = calculate_sla(ticket.priority, ticket.created_at)
    ticket.response_deadline = response_deadline
    ticket.resolution_deadline = resolution_deadline
    return ticket


def update_priority(ticket: Ticket, priority: TicketPriority) -> Ticket:
    ticket.priority = priority
    return refresh_sla(ticket)
