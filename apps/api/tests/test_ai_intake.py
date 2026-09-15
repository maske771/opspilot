from app.ai_intake import classify
from app.models import TicketPriority


def test_intake_classifies_critical_fire():
    result = classify("There is a fire in the kitchen")
    assert result.category == "emergency"
    assert result.priority == TicketPriority.CRITICAL
    assert result.confidence > 0.9


def test_intake_classifies_russian_plumbing():
    result = classify("В ванной течет вода из крана")
    assert result.category == "plumbing"
    assert result.priority == TicketPriority.HIGH


def test_intake_falls_back_to_other():
    result = classify("I need some information about the apartment")
    assert result.category == "other"
    assert result.priority == TicketPriority.MEDIUM


def test_intake_classifies_electrical():
    result = classify("The power socket is broken")
    assert result.category == "electrical"
    assert result.priority == TicketPriority.HIGH
