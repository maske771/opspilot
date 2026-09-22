from dataclasses import dataclass
from typing import Literal, Protocol

Language = Literal["en", "ru"]

STATUS_KEYWORDS = (
    "status", "update", "when", "how long", "progress", "eta",
    "статус", "когда", "как дела", "готово", "обновлен", "сколько ждать", "что там",
)


def detect_language(text: str) -> Language:
    if any("а" <= ch.lower() <= "я" or ch.lower() == "ё" for ch in text):
        return "ru"
    return "en"


def is_status_query(text: str) -> bool:
    lowered = text.lower()
    return any(keyword in lowered for keyword in STATUS_KEYWORDS)


@dataclass(frozen=True)
class GeneratedResponse:
    text: str
    provider: str
    confidence: float


class ResponseGenerator(Protocol):
    def generate(self, *, customer_message: str, category: str, priority: str, language: Language = "en") -> GeneratedResponse: ...
    def generate_follow_up(self, *, customer_message: str, ticket_status: str, language: Language = "en") -> GeneratedResponse: ...


_INTAKE_TEMPLATES: dict[Language, dict[str, str]] = {
    "en": {
        "critical": "We received your urgent request and have marked it as critical. Our team will review it as soon as possible.",
        "plumbing": "We received your plumbing request. Please tell us whether water is actively leaking and, if possible, where the leak is located.",
        "electrical": "We received your electrical request. If there is smoke, fire, sparking, or an immediate safety risk, move to a safe location and contact emergency services.",
        "default": "We received your request. Our team has registered it and will review the details shortly.",
    },
    "ru": {
        "critical": "Мы получили ваш срочный запрос и отметили его как критический. Наша команда рассмотрит его как можно скорее.",
        "plumbing": "Мы получили ваш запрос по сантехнике. Подскажите, есть ли сейчас активная протечка воды и где именно.",
        "electrical": "Мы получили ваш запрос по электрике. Если есть дым, искры или угроза безопасности — отойдите в безопасное место и обратитесь в экстренные службы.",
        "default": "Мы получили ваш запрос. Наша команда зарегистрировала его и скоро рассмотрит детали.",
    },
}

_STATUS_PHRASES: dict[Language, dict[str, str]] = {
    "en": {
        "new": "Your request is in our queue and will be assigned shortly.",
        "assigned": "Your request has been assigned to our team.",
        "accepted": "Our team has accepted your request and will begin shortly.",
        "in_progress": "Our team is actively working on your request right now.",
        "completed": "Your request has been marked as completed by our team.",
        "waiting_approval": "Your request is completed and pending final review.",
        "closed": "This request has been closed. Let us know if you need anything else.",
    },
    "ru": {
        "new": "Ваш запрос в очереди и скоро будет назначен исполнителю.",
        "assigned": "Ваш запрос назначен нашей команде.",
        "accepted": "Наша команда приняла ваш запрос и скоро приступит к работе.",
        "in_progress": "Наша команда сейчас активно работает над вашим запросом.",
        "completed": "Ваш запрос отмечен как выполненный.",
        "waiting_approval": "Работа по вашему запросу завершена и ожидает финальной проверки.",
        "closed": "Этот запрос закрыт. Дайте знать, если понадобится что-то ещё.",
    },
}

_FOLLOW_UP_ACK: dict[Language, str] = {
    "en": "Got it, thanks for the extra details — we've added this to your existing request.",
    "ru": "Спасибо, добавили это к вашему текущему запросу.",
}

_THANKS_WORDS = ("thanks", "thank you", "thx", "ty", "спасибо", "благодар")

_GREETING_REPLIES: dict[Language, dict[str, str]] = {
    "en": {
        "thanks": "You're welcome! Reach out anytime you need something.",
        "hello": "Hello! How can we help you today?",
    },
    "ru": {
        "thanks": "Пожалуйста! Обращайтесь, если понадобится что-то ещё.",
        "hello": "Здравствуйте! Чем можем помочь?",
    },
}


def generate_greeting(*, customer_message: str, language: Language = "en") -> GeneratedResponse:
    language = language if language in _GREETING_REPLIES else "en"
    kind = "thanks" if any(word in customer_message.lower() for word in _THANKS_WORDS) else "hello"
    return GeneratedResponse(text=_GREETING_REPLIES[language][kind], provider="rule-based", confidence=0.6)


class RuleBasedResponseGenerator:
    """Safe deterministic baseline used until an external LLM provider is configured."""

    def generate(self, *, customer_message: str, category: str, priority: str, language: Language = "en") -> GeneratedResponse:
        templates = _INTAKE_TEMPLATES.get(language, _INTAKE_TEMPLATES["en"])
        if priority == "critical":
            text = templates["critical"]
        elif category in templates:
            text = templates[category]
        else:
            text = templates["default"]
        return GeneratedResponse(text=text, provider="rule-based", confidence=0.82)

    def generate_follow_up(self, *, customer_message: str, ticket_status: str, language: Language = "en") -> GeneratedResponse:
        language = language if language in _STATUS_PHRASES else "en"
        if is_status_query(customer_message):
            text = _STATUS_PHRASES[language].get(ticket_status, _STATUS_PHRASES[language]["new"])
            return GeneratedResponse(text=text, provider="rule-based", confidence=0.75)
        return GeneratedResponse(text=_FOLLOW_UP_ACK[language], provider="rule-based", confidence=0.7)


def get_response_generator() -> ResponseGenerator:
    # Provider selection is intentionally isolated so an LLM can be added without changing the API contract.
    return RuleBasedResponseGenerator()
