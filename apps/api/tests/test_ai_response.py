from app.ai_response import RuleBasedResponseGenerator, detect_language, generate_greeting, is_status_query


def test_detect_language_russian():
    assert detect_language("Кондиционер не работает") == "ru"


def test_detect_language_english():
    assert detect_language("The air conditioner is broken") == "en"


def test_is_status_query_detects_english_keywords():
    assert is_status_query("any update on this?")
    assert is_status_query("what's the status")
    assert not is_status_query("also the bathroom light is flickering")


def test_is_status_query_detects_russian_keywords():
    assert is_status_query("какой статус по заявке?")
    assert is_status_query("когда починят")
    assert not is_status_query("ещё на кухне не горит свет")


def test_generate_does_not_leak_ticket_jargon():
    generator = RuleBasedResponseGenerator()
    result = generator.generate(customer_message="water leak", category="plumbing", priority="high", language="en")
    assert "ticket" not in result.text.lower()
    assert "#" not in result.text


def test_generate_critical_overrides_category():
    generator = RuleBasedResponseGenerator()
    result = generator.generate(customer_message="fire!", category="plumbing", priority="critical", language="en")
    assert "critical" in result.text.lower()


def test_generate_follow_up_status_query_uses_status_phrase():
    generator = RuleBasedResponseGenerator()
    result = generator.generate_follow_up(customer_message="any update?", ticket_status="in_progress", language="en")
    assert "working on" in result.text.lower()


def test_generate_follow_up_non_status_uses_generic_ack():
    generator = RuleBasedResponseGenerator()
    result = generator.generate_follow_up(customer_message="also the light is broken", ticket_status="in_progress", language="en")
    assert "added" in result.text.lower()


def test_generate_follow_up_russian():
    generator = RuleBasedResponseGenerator()
    result = generator.generate_follow_up(customer_message="какой статус?", ticket_status="closed", language="ru")
    assert "закрыт" in result.text.lower()


def test_generate_falls_back_to_english_for_unsupported_language():
    generator = RuleBasedResponseGenerator()
    result = generator.generate(customer_message="x", category="other", priority="low", language="th")
    assert result.text == RuleBasedResponseGenerator().generate(customer_message="x", category="other", priority="low", language="en").text


def test_generate_greeting_thanks():
    result = generate_greeting(customer_message="thanks!", language="en")
    assert "welcome" in result.text.lower()


def test_generate_greeting_hello():
    result = generate_greeting(customer_message="hi there", language="en")
    assert "help" in result.text.lower()


def test_generate_greeting_russian_thanks():
    result = generate_greeting(customer_message="спасибо большое", language="ru")
    assert "пожалуйста" in result.text.lower()
