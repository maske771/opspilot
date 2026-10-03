import re
from dataclasses import dataclass
from typing import Literal, Protocol

from .ai_intake import FALLBACK_CODE, is_status_query

__all__ = ["is_status_query"]  # re-exported for callers that only deal with replies

Language = Literal["en", "ru", "th"]
LANGUAGES: tuple[Language, ...] = ("en", "ru", "th")

_CYRILLIC = re.compile(r"[а-яё]", re.IGNORECASE)
_THAI = re.compile(r"[฀-๿]")


def detect_language(text: str) -> Language:
    if _THAI.search(text):
        return "th"
    if _CYRILLIC.search(text):
        return "ru"
    return "en"


def has_language_signal(text: str) -> bool:
    """False for messages that say nothing about the language: a property code, a photo, digits."""
    return bool(_THAI.search(text) or _CYRILLIC.search(text) or re.search(r"[a-z]{2,}\s+[a-z]{2,}", text.lower()))


@dataclass(frozen=True)
class GeneratedResponse:
    text: str
    provider: str
    confidence: float


class ResponseGenerator(Protocol):
    def generate(self, *, customer_message: str, category: str, priority: str, language: Language = "en", has_media: bool = False) -> GeneratedResponse: ...
    def generate_follow_up(
        self, *, customer_message: str, ticket_status: str, language: Language = "en", category: str | None = None, has_media: bool = False
    ) -> GeneratedResponse: ...


# A photo helps almost every category — including "other", where the classifier had no keyword match
# and a photo is often the fastest way to actually find out what's wrong. The one exception is
# "emergency": don't delay a safety response by asking for a photo.
NO_PHOTO_REQUEST_CATEGORIES = {"emergency"}

_PHOTO_REQUEST: dict[Language, str] = {
    "en": "If you can, please also send a photo of the issue — it helps our team respond faster.",
    "ru": "Если можете, пришлите, пожалуйста, фото проблемы — это поможет нашей команде быстрее отреагировать.",
    "th": "หากสะดวก รบกวนส่งรูปปัญหามาด้วย จะช่วยให้ทีมงานดำเนินการได้เร็วขึ้น",
}

_INTAKE_TEMPLATES: dict[Language, dict[str, str]] = {
    "en": {
        "emergency": "We received your emergency report and alerted our team. If there is any immediate danger, get to a safe place and call the emergency services.",
        "critical": "We received your urgent request and have marked it as critical. Our team will review it as soon as possible.",
        "plumbing": "We received your plumbing request. Please tell us whether water is actively leaking and, if possible, where the leak is located.",
        "electrical": "We received your electrical request. If there is smoke, fire, sparking, or an immediate safety risk, move to a safe location and contact emergency services.",
        FALLBACK_CODE: "We received your request. Please describe the problem in a bit more detail: what exactly happened and where?",
        "default": "We received your request. Our team has registered it and will review the details shortly.",
    },
    "ru": {
        "emergency": "Мы получили сообщение об аварии и оповестили команду. Если есть непосредственная опасность — уйдите в безопасное место и вызовите экстренные службы.",
        "critical": "Мы получили ваш срочный запрос и отметили его как критический. Наша команда рассмотрит его как можно скорее.",
        "plumbing": "Мы получили ваш запрос по сантехнике. Подскажите, есть ли сейчас активная протечка воды и где именно.",
        "electrical": "Мы получили ваш запрос по электрике. Если есть дым, искры или угроза безопасности — отойдите в безопасное место и обратитесь в экстренные службы.",
        FALLBACK_CODE: "Мы получили ваш запрос. Опишите, пожалуйста, проблему чуть подробнее: что именно случилось и где?",
        "default": "Мы получили ваш запрос. Наша команда зарегистрировала его и скоро рассмотрит детали.",
    },
    "th": {
        "emergency": "เราได้รับแจ้งเหตุฉุกเฉินแล้วและแจ้งทีมงานทันที หากมีอันตราย กรุณาออกไปยังที่ปลอดภัยและโทรแจ้งหน่วยฉุกเฉิน",
        "critical": "เราได้รับคำขอเร่งด่วนของคุณแล้วและจัดเป็นเรื่องด่วนที่สุด ทีมงานจะดำเนินการโดยเร็วที่สุด",
        "plumbing": "เราได้รับแจ้งปัญหาระบบประปาแล้ว ตอนนี้น้ำยังรั่วอยู่หรือไม่ และรั่วที่จุดไหน",
        "electrical": "เราได้รับแจ้งปัญหาระบบไฟฟ้าแล้ว หากมีควัน ไฟลุก ประกายไฟ หรืออันตราย กรุณาออกไปยังที่ปลอดภัยและติดต่อหน่วยฉุกเฉิน",
        FALLBACK_CODE: "เราได้รับคำขอของคุณแล้ว รบกวนอธิบายปัญหาเพิ่มเติมอีกนิด ว่าเกิดอะไรขึ้นและที่จุดไหน",
        "default": "เราได้รับคำขอของคุณแล้ว ทีมงานได้บันทึกไว้และจะตรวจสอบรายละเอียดเร็วๆ นี้",
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
        "none": "We don't see any requests from you yet. Describe the problem and we'll register it.",
    },
    "ru": {
        "new": "Ваш запрос в очереди и скоро будет назначен исполнителю.",
        "assigned": "Ваш запрос назначен нашей команде.",
        "accepted": "Наша команда приняла ваш запрос и скоро приступит к работе.",
        "in_progress": "Наша команда сейчас активно работает над вашим запросом.",
        "completed": "Ваш запрос отмечен как выполненный.",
        "waiting_approval": "Работа по вашему запросу завершена и ожидает финальной проверки.",
        "closed": "Этот запрос закрыт. Дайте знать, если понадобится что-то ещё.",
        "none": "У нас пока нет ваших заявок. Опишите проблему — и мы её зарегистрируем.",
    },
    "th": {
        "new": "คำขอของคุณอยู่ในคิวและจะมอบหมายให้ช่างเร็วๆ นี้",
        "assigned": "คำขอของคุณได้มอบหมายให้ทีมงานแล้ว",
        "accepted": "ทีมงานรับเรื่องของคุณแล้วและจะเริ่มดำเนินการเร็วๆ นี้",
        "in_progress": "ทีมงานกำลังดำเนินการตามคำขอของคุณอยู่",
        "completed": "คำขอของคุณดำเนินการเสร็จเรียบร้อยแล้ว",
        "waiting_approval": "งานตามคำขอของคุณเสร็จแล้วและรอการตรวจสอบขั้นสุดท้าย",
        "closed": "คำขอนี้ปิดแล้ว หากต้องการความช่วยเหลือเพิ่มเติม แจ้งเราได้เลย",
        "none": "ยังไม่มีคำขอจากคุณ เล่าปัญหาให้เราฟัง แล้วเราจะบันทึกให้",
    },
}

_FOLLOW_UP_ACK: dict[Language, str] = {
    "en": "Got it, thanks for the extra details — we've added this to your existing request.",
    "ru": "Спасибо, добавили это к вашему текущему запросу.",
    "th": "รับทราบ ขอบคุณสำหรับข้อมูลเพิ่มเติม เราได้เพิ่มไว้ในคำขอเดิมของคุณแล้ว",
}

_THANKS_WORDS = ("thanks", "thank you", "thx", "ty", "спасибо", "благодар", "ขอบคุณ", "ขอบใจ")

_GREETING_REPLIES: dict[Language, dict[str, str]] = {
    "en": {
        "thanks": "You're welcome! Reach out anytime you need something.",
        "hello": "Hello! How can we help you today?",
        "ack": "Thank you! We'll keep you posted.",
    },
    "ru": {
        "thanks": "Пожалуйста! Обращайтесь, если понадобится что-то ещё.",
        "hello": "Здравствуйте! Чем можем помочь?",
        "ack": "Спасибо! Будем держать вас в курсе.",
    },
    "th": {
        "thanks": "ยินดีครับ หากต้องการความช่วยเหลือ ติดต่อเราได้ตลอดเวลา",
        "hello": "สวัสดีครับ มีอะไรให้เราช่วยไหมครับ",
        "ack": "ขอบคุณครับ เราจะแจ้งความคืบหน้าให้ทราบ",
    },
}


_REGISTRATION: dict[Language, dict[str, str]] = {
    "en": {
        "ask_code": "Welcome! To get started, please send the property code your property manager gave you. If you don't have one, ask your manager.",
        "code_not_found": "We couldn't find a property with that code. Please check it and send it again — or ask your property manager for the code.",
        "linked": "Thanks! You're now registered at {property}.",
        "linked_how_can_we_help": "Thanks! You're now registered at {property}. How can we help?",
    },
    "ru": {
        "ask_code": "Здравствуйте! Чтобы начать, пришлите, пожалуйста, код объекта, который вам выдал управляющий. Если кода нет — уточните его у управляющего.",
        "code_not_found": "Не нашли объект с таким кодом. Проверьте код и пришлите его ещё раз — или уточните его у управляющего.",
        "linked": "Спасибо! Вы зарегистрированы на объекте {property}.",
        "linked_how_can_we_help": "Спасибо! Вы зарегистрированы на объекте {property}. Чем можем помочь?",
    },
    "th": {
        "ask_code": "ยินดีต้อนรับ! กรุณาส่งรหัสอาคารที่ได้รับจากผู้จัดการอาคารเพื่อเริ่มใช้งาน หากยังไม่มีรหัส สอบถามได้ที่ผู้จัดการอาคาร",
        "code_not_found": "ไม่พบอาคารที่ใช้รหัสนี้ กรุณาตรวจสอบแล้วส่งอีกครั้ง หรือสอบถามรหัสจากผู้จัดการอาคาร",
        "linked": "ขอบคุณ! ลงทะเบียนกับ {property} เรียบร้อยแล้ว",
        "linked_how_can_we_help": "ขอบคุณ! ลงทะเบียนกับ {property} เรียบร้อยแล้ว มีอะไรให้เราช่วยไหม",
    },
}


def _lang(language: str) -> Language:
    return language if language in LANGUAGES else "en"  # type: ignore[return-value]


def registration_text(kind: str, language: Language = "en", **values: str) -> str:
    return _REGISTRATION[_lang(language)][kind].format(**values)


def status_text(ticket_status: str | None, language: Language = "en") -> str:
    """Answer to "any update?" — `None` when the customer has no tickets at all."""
    phrases = _STATUS_PHRASES[_lang(language)]
    return phrases.get(ticket_status or "none", phrases["new"])


def generate_greeting(*, customer_message: str, language: Language = "en", has_open_ticket: bool = False) -> GeneratedResponse:
    """Small talk. With a request already open, "ok"/"thanks" is an acknowledgement, not a new conversation."""
    replies = _GREETING_REPLIES[_lang(language)]
    if any(word in customer_message.lower() for word in _THANKS_WORDS):
        kind = "thanks"
    else:
        kind = "ack" if has_open_ticket else "hello"
    return GeneratedResponse(text=replies[kind], provider="rule-based", confidence=0.6)


class RuleBasedResponseGenerator:
    """Safe deterministic baseline used until an external LLM provider is configured."""

    def generate(self, *, customer_message: str, category: str, priority: str, language: Language = "en", has_media: bool = False) -> GeneratedResponse:
        language = _lang(language)
        templates = _INTAKE_TEMPLATES[language]
        if category == "emergency":
            text = templates["emergency"]
        elif priority == "critical":
            text = templates["critical"]
        elif category in templates:
            text = templates[category]
        else:
            text = templates["default"]
        if not has_media and category not in NO_PHOTO_REQUEST_CATEGORIES:
            text = f"{text}\n\n{_PHOTO_REQUEST[language]}"
        return GeneratedResponse(text=text, provider="rule-based", confidence=0.82)

    def generate_follow_up(
        self, *, customer_message: str, ticket_status: str, language: Language = "en", category: str | None = None, has_media: bool = False
    ) -> GeneratedResponse:
        language = _lang(language)
        if is_status_query(customer_message):
            return GeneratedResponse(text=status_text(ticket_status, language), provider="rule-based", confidence=0.75)
        text = _FOLLOW_UP_ACK[language]
        if not has_media and category not in NO_PHOTO_REQUEST_CATEGORIES:
            text = f"{text}\n\n{_PHOTO_REQUEST[language]}"
        return GeneratedResponse(text=text, provider="rule-based", confidence=0.7)


def get_response_generator() -> ResponseGenerator:
    # Provider selection is intentionally isolated so an LLM can be added without changing the API contract.
    return RuleBasedResponseGenerator()
