import re
from dataclasses import dataclass

from .models import TicketPriority


@dataclass(frozen=True)
class IntakeResult:
    category: str
    priority: TicketPriority
    confidence: float
    reason: str


@dataclass(frozen=True)
class ServiceRule:
    code: str
    keywords: tuple[str, ...]
    priority: TicketPriority


FALLBACK_CODE = "other"

# The out-of-the-box catalog. An organization's services are seeded from this (see services.py) and
# then edited in the UI; these rules are only used directly when no organization is in scope.
# Matching is by substring (Russian stems, Thai has no spaces), so Thai keywords are kept specific:
# a bare "น้ำ" (water) would also match "ห้องน้ำ" (bathroom).
# Keywords added here later must also reach existing organizations through a migration (see 021).
DEFAULT_RULES = (
    ServiceRule(
        "emergency",
        ("fire", "flood", "gas", "smoke", "пожар", "затоп", "газ", "ไฟไหม้", "ควัน", "แก๊ส", "น้ำท่วม"),
        TicketPriority.CRITICAL,
    ),
    ServiceRule(
        "plumbing",
        ("water", "leak", "toilet", "sink", "вода", "теч", "унитаз", "кран", "รั่ว", "ท่อ", "ชักโครก", "ส้วม", "ก๊อก", "อ่างล้าง", "น้ำไม่ไหล"),
        TicketPriority.HIGH,
    ),
    ServiceRule(
        "electrical",
        (
            "electric", "socket", "outlet", "power", "light", "spark", "электр", "розет", "свет", "искр",
            "ไฟฟ้า", "ไฟดับ", "ไฟไม่ติด", "ปลั๊ก", "สวิตช์", "หลอดไฟ", "ไฟช็อต",
        ),
        TicketPriority.HIGH,
    ),
    ServiceRule(
        "hvac",
        ("air conditioner", "ac ", "heating", "cooling", "кондиционер", "отоплен", "тепло", "холодно", "แอร์", "เครื่องปรับอากาศ", "ไม่เย็น"),
        TicketPriority.MEDIUM,
    ),
    ServiceRule(
        "appliance",
        ("fridge", "refrigerator", "washing machine", "oven", "холодильник", "стирал", "духов", "ตู้เย็น", "เครื่องซักผ้า", "เตาอบ", "ไมโครเวฟ", "เครื่องทำน้ำอุ่น"),
        TicketPriority.MEDIUM,
    ),
    ServiceRule(
        "access",
        ("key", "lock", "door", "access", "ключ", "замок", "дверь", "доступ", "กุญแจ", "ประตู", "ล็อค", "ล็อก", "คีย์การ์ด"),
        TicketPriority.HIGH,
    ),
)

# Messages made only of these (plus punctuation/emoji) are small talk, not requests. Thai polite
# particles (ครับ/ค่ะ/...) are listed on their own because they attach to any phrase.
SMALL_TALK_PHRASES = (
    "hi", "hello", "hey", "yo", "there", "thanks", "thank you", "thank", "you", "thx", "ty", "ok", "okay", "cool", "nice", "great",
    "good morning", "good evening", "good afternoon", "good night", "yes", "no", "please", "you're welcome", "bye", "goodbye",
    "got it", "sure", "perfect", "much", "so", "a lot", "all", "everyone", "team",
    "привет", "здравствуйте", "здравствуй", "добрый день", "добрый вечер", "доброе утро", "хай", "спасибо", "большое",
    "благодарю", "пожалуйста", "ок", "окей", "хорошо", "понятно", "ясно", "ага", "угу", "да", "нет", "отлично", "супер",
    "пока", "до свидания", "всего доброго", "понял", "поняла", "жду", "ждём",
    "สวัสดี", "ขอบคุณ", "ขอบใจ", "โอเค", "ได้", "ครับผม", "ครับ", "ค่ะ", "คะ", "ค่า", "นะ", "จ้า", "มาก",
)
_SMALL_TALK = sorted(SMALL_TALK_PHRASES, key=len, reverse=True)

STATUS_KEYWORDS = (
    "status", "update", "when", "how long", "progress", "eta", "any news",
    "статус", "когда", "как дела", "готово", "обновлен", "сколько ждать", "что там", "что с заявк", "новости",
    "สถานะ", "เมื่อไหร่", "เมื่อไร", "ถึงไหน", "นานไหม", "กี่โมง",
)

_SEVERITY = {TicketPriority.CRITICAL: 0, TicketPriority.HIGH: 1, TicketPriority.MEDIUM: 2, TicketPriority.LOW: 3}
_THAI = re.compile(r"[฀-๿]")


def _normalize(text: str) -> str:
    return f" {text.lower().strip()} "


def matched_rule(text: str, rules=DEFAULT_RULES) -> ServiceRule | None:
    """The service whose keyword appears in the text; more severe services are checked first so
    e.g. "gas leak" lands in emergency rather than plumbing."""
    normalized = _normalize(text)
    for rule in sorted(rules, key=lambda r: _SEVERITY[r.priority]):
        if any(keyword and keyword.lower() in normalized for keyword in rule.keywords):
            return rule
    return None


def classify(text: str, rules=DEFAULT_RULES, fallback_priority: TicketPriority = TicketPriority.MEDIUM) -> IntakeResult:
    rule = matched_rule(text, rules)
    if rule is not None:
        return IntakeResult(rule.code, rule.priority, 0.95, f"matched {rule.code} keyword")
    return IntakeResult(FALLBACK_CODE, fallback_priority, 0.55, "no service keyword matched")


def is_small_talk(text: str) -> bool:
    """True when the message is nothing but greetings, thanks and acknowledgements."""
    remaining = re.sub(r"[^\w฀-๿' ]+", " ", text.lower())
    for phrase in _SMALL_TALK:
        if _THAI.search(phrase):
            remaining = remaining.replace(phrase, " ")
        else:
            remaining = re.sub(rf"(?<![\w']){re.escape(phrase)}(?![\w'])", " ", remaining)
    return not re.search(r"[^\W\d_]", remaining)


def is_status_query(text: str) -> bool:
    """"When will someone come?" — but not "it sparks when I turn on the kettle, second day now".
    A status word counts when the message is a question or too short to be a description."""
    lowered = text.lower()
    if not any(keyword in lowered for keyword in STATUS_KEYWORDS):
        return False
    return lowered.rstrip().endswith("?") or len(lowered.split()) <= 4


def is_actionable_request(text: str, rules=DEFAULT_RULES) -> bool:
    """False for small talk (greetings/thanks/short acknowledgements) that shouldn't spawn a ticket."""
    if matched_rule(text, rules) is not None:
        return True
    stripped = text.strip().lower().rstrip("!.,? ")
    if len(stripped) <= 3:
        return False
    return not is_small_talk(text)
