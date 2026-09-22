from app.ai_intake import classify, is_actionable_request
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


def test_greetings_are_not_actionable():
    assert not is_actionable_request("hi")
    assert not is_actionable_request("привет")
    assert not is_actionable_request("thanks!")
    assert not is_actionable_request("спасибо большое")
    assert not is_actionable_request("ok")
    assert not is_actionable_request("ок")


def test_real_requests_are_actionable():
    assert is_actionable_request("There is a fire in the kitchen")
    assert is_actionable_request("В ванной течет вода из крана")
    assert is_actionable_request("My washing machine is not working properly")


def test_greeting_containing_a_real_issue_is_actionable():
    assert is_actionable_request("hi, the water is leaking everywhere")


def test_ambiguous_non_greeting_text_is_actionable():
    assert is_actionable_request("у меня проблема в квартире, можете помочь")
