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
DEFAULT_RULES = (
    ServiceRule("emergency", ("fire", "flood", "gas", "smoke", "пожар", "затоп", "газ"), TicketPriority.CRITICAL),
    ServiceRule("plumbing", ("water", "leak", "toilet", "sink", "вода", "теч", "унитаз", "кран"), TicketPriority.HIGH),
    ServiceRule("electrical", ("electric", "socket", "outlet", "power", "light", "электр", "розет", "свет"), TicketPriority.HIGH),
    ServiceRule("hvac", ("air conditioner", "ac ", "heating", "cooling", "кондиционер", "отоплен", "тепло", "холодно"), TicketPriority.MEDIUM),
    ServiceRule("appliance", ("fridge", "refrigerator", "washing machine", "oven", "холодильник", "стирал", "духов"), TicketPriority.MEDIUM),
    ServiceRule("access", ("key", "lock", "door", "access", "ключ", "замок", "дверь", "доступ"), TicketPriority.HIGH),
)

GREETING_PHRASES = (
    "hi", "hello", "hey", "yo", "thanks", "thank you", "thx", "ty", "ok", "okay", "cool", "nice", "great",
    "good morning", "good evening", "good afternoon", "yes", "no", "please", "you're welcome",
    "привет", "здравствуйте", "здравствуй", "добрый день", "добрый вечер", "доброе утро", "хай",
    "спасибо", "благодарю", "пожалуйста", "ок", "окей", "хорошо", "понятно", "ясно", "ага", "угу", "да", "нет",
)

_SEVERITY = {TicketPriority.CRITICAL: 0, TicketPriority.HIGH: 1, TicketPriority.MEDIUM: 2, TicketPriority.LOW: 3}


def classify(text: str, rules=DEFAULT_RULES, fallback_priority: TicketPriority = TicketPriority.MEDIUM) -> IntakeResult:
    """First matching service wins; more severe services are checked first so e.g. "gas leak"
    lands in emergency rather than plumbing."""
    normalized = f" {text.lower().strip()} "
    for rule in sorted(rules, key=lambda r: _SEVERITY[r.priority]):
        if any(keyword and keyword.lower() in normalized for keyword in rule.keywords):
            return IntakeResult(rule.code, rule.priority, 0.95, f"matched {rule.code} keyword")
    return IntakeResult(FALLBACK_CODE, fallback_priority, 0.55, "no service keyword matched")


def is_actionable_request(text: str, rules=DEFAULT_RULES) -> bool:
    """False for small talk (greetings/thanks/short acknowledgements) that shouldn't spawn a ticket."""
    normalized = f" {text.lower().strip()} "
    if any(keyword and keyword.lower() in normalized for rule in rules for keyword in rule.keywords):
        return True
    stripped = text.strip().lower().rstrip("!.,? ")
    if len(stripped) <= 3:
        return False
    return not any(stripped == phrase or stripped.startswith(phrase + " ") for phrase in GREETING_PHRASES)
