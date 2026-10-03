"""The customer dialog, scenario by scenario: what the bot should do in each situation a real
chat runs into. Each test is one line of the checklist."""
import pytest
from sqlalchemy import select

from app.models import Ticket, TicketStatus
from tests.test_registration import Chat, setup

PHOTO_RU = "фото"
PHOTO_EN = "photo"


def chat(db_session, with_property=False):
    org, _, channel, prop = setup(db_session, with_property=with_property)
    return Chat(db_session, org, channel), prop


def tickets(db_session, c):
    return list(db_session.scalars(select(Ticket).where(Ticket.organization_id == c.org.id).order_by(Ticket.created_at)))


def close(db_session, ticket, status=TicketStatus.CLOSED):
    ticket.status = status
    db_session.commit()


# --- small talk ---------------------------------------------------------------------------------

@pytest.mark.parametrize("text", ["Привет", "Здравствуйте!", "hello", "Добрый день", "ok", "спасибо", "สวัสดีครับ", "ขอบคุณค่ะ"])
def test_small_talk_without_a_ticket_gets_a_greeting_and_no_ticket(db_session, text):
    c, _ = chat(db_session)
    reply, ticket, created = c.send(text)
    assert not created and ticket is None and reply


@pytest.mark.parametrize(
    "text",
    ["Привет, у меня сломался шкаф", "hello, my wardrobe is broken", "Добрый день, не работает лифт", "hi there, the gate does not open"],
)
def test_a_greeting_followed_by_a_problem_opens_a_ticket(db_session, text):
    c, _ = chat(db_session)
    _, _, created = c.send(text)
    assert created


def test_thanks_on_an_open_ticket_is_not_treated_as_new_details(db_session):
    c, _ = chat(db_session)
    c.send("течёт кран")
    reply, _, created = c.send("спасибо!")
    assert not created
    assert "добавили" not in reply.lower() and PHOTO_RU not in reply.lower()


def test_ok_on_an_open_ticket_gets_a_short_reply_without_a_photo_request(db_session):
    c, _ = chat(db_session)
    c.send("the toilet is leaking")
    reply, _, _ = c.send("ok")
    assert PHOTO_EN not in reply.lower()


# --- status questions ---------------------------------------------------------------------------

def test_status_question_on_an_open_ticket_answers_with_the_status(db_session):
    c, _ = chat(db_session)
    c.send("течёт кран")
    reply, _, created = c.send("когда придёт мастер?")
    assert not created and "назначен" in reply.lower()


def test_status_question_without_any_ticket_does_not_open_one(db_session):
    c, _ = chat(db_session)
    _, _, created = c.send("ну что там с моей заявкой?")
    assert not created


def test_status_question_after_the_ticket_was_closed_says_it_is_closed(db_session):
    c, _ = chat(db_session)
    _, ticket, _ = c.send("течёт кран")
    close(db_session, ticket)
    reply, _, created = c.send("какой статус?")
    assert not created and "закрыт" in reply.lower()


def test_details_mentioning_when_are_not_mistaken_for_a_status_question(db_session):
    c, _ = chat(db_session)
    c.send("искрит розетка")
    reply, _, _ = c.send("искрит когда включаю чайник, уже второй день")
    assert "добавили" in reply.lower()


# --- tickets --------------------------------------------------------------------------------------

def test_a_different_problem_while_a_ticket_is_open_gets_its_own_ticket(db_session):
    c, _ = chat(db_session)
    _, first, _ = c.send("течёт кран на кухне")
    _, second, created = c.send("и ещё не работает кондиционер в спальне")
    assert created and second.id != first.id and second.category == "hvac"


def test_more_details_on_the_same_problem_stay_on_the_same_ticket(db_session):
    c, _ = chat(db_session)
    _, first, _ = c.send("течёт кран на кухне")
    _, same, created = c.send("вода уже на полу")
    assert not created and same.id == first.id


def test_a_new_problem_after_the_work_is_completed_opens_a_new_ticket(db_session):
    c, _ = chat(db_session)
    _, first, _ = c.send("течёт кран")
    close(db_session, first, TicketStatus.COMPLETED)
    _, second, created = c.send("теперь не работает свет в ванной")
    assert created and second.id != first.id


def test_a_photo_without_text_opens_a_ticket_and_does_not_ask_for_a_photo(db_session):
    c, _ = chat(db_session)
    reply, ticket, created = c.send("", media=True)
    assert created and ticket is not None
    assert "photo" not in reply.lower() and PHOTO_RU not in reply.lower()


def test_emergency_reply_gives_safety_advice_and_no_photo_request(db_session):
    c, _ = chat(db_session)
    reply, ticket, _ = c.send("пожар в коридоре!")
    assert ticket.category == "emergency"
    assert PHOTO_RU not in reply.lower() and "безопасн" in reply.lower()


def test_vague_problem_opens_a_ticket_and_asks_what_is_wrong(db_session):
    c, _ = chat(db_session)
    reply, ticket, created = c.send("у меня проблема")
    assert created and ticket.category == "other"
    assert "опишите" in reply.lower() or "подробн" in reply.lower()


# --- languages ------------------------------------------------------------------------------------

def test_thai_request_is_classified_and_answered_in_thai(db_session):
    c, _ = chat(db_session)
    reply, ticket, created = c.send("แอร์ไม่เย็นครับ")
    assert created and ticket.category == "hvac"
    assert any("฀" <= ch <= "๿" for ch in reply)


@pytest.mark.parametrize(
    "text, category",
    [("น้ำรั่วในห้องน้ำ", "plumbing"), ("ไฟดับทั้งห้อง", "electrical"), ("ตู้เย็นเสีย", "appliance"), ("ลืมกุญแจ", "access"), ("ไฟไหม้!", "emergency")],
)
def test_thai_keywords_pick_the_right_service(db_session, text, category):
    c, _ = chat(db_session)
    _, ticket, _ = c.send(text)
    assert ticket.category == category


def test_thai_registration_asks_for_the_code_in_thai(db_session):
    c, _ = chat(db_session, with_property=True)
    reply, _, _ = c.send("น้ำรั่วครับ")
    assert any("฀" <= ch <= "๿" for ch in reply)
    reply, ticket, created = c.send("K7PX2M")
    assert created and any("฀" <= ch <= "๿" for ch in reply)


def test_language_sticks_to_the_conversation_for_a_bare_code_or_photo(db_session):
    c, _ = chat(db_session)
    c.send("แอร์ไม่เย็น")
    reply, _, _ = c.send("", media=True)
    assert any("฀" <= ch <= "๿" for ch in reply)


def test_english_follow_up_replies_in_english(db_session):
    c, _ = chat(db_session)
    c.send("my sink is leaking")
    reply, _, _ = c.send("any update?")
    assert all(not ("а" <= ch.lower() <= "я") for ch in reply)


def test_the_explanation_after_a_vague_message_re_sorts_the_same_ticket(db_session):
    c, _ = chat(db_session)
    _, vague, _ = c.send("у меня проблема")
    reply, same, created = c.send("течёт кран на кухне")
    assert not created and same.id == vague.id
    assert same.category == "plumbing" and same.title == "течёт кран на кухне"
    assert "сантехник" in reply.lower()
    assert len(tickets(db_session, c)) == 1


def test_a_question_about_a_problem_with_no_tickets_yet_opens_one(db_session):
    c, _ = chat(db_session)
    _, ticket, created = c.send("когда сможете починить кран?")
    assert created and ticket.category == "plumbing"
