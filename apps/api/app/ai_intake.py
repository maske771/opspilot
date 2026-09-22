from dataclasses import dataclass

from .models import TicketPriority


@dataclass(frozen=True)
class IntakeResult:
    category: str
    priority: TicketPriority
    confidence: float
    reason: str


RULES = (
    ("emergency", ("fire", "flood", "gas", "smoke", "пожар", "затоп", "газ"), TicketPriority.CRITICAL, 0.97),
    ("plumbing", ("water", "leak", "toilet", "sink", "вода", "теч", "унитаз", "кран"), TicketPriority.HIGH, 0.91),
    ("electrical", ("electric", "socket", "outlet", "power", "light", "электр", "розет", "свет"), TicketPriority.HIGH, 0.90),
    ("hvac", ("air conditioner", "ac ", "heating", "cooling", "кондиционер", "отоплен", "тепло", "холодно"), TicketPriority.MEDIUM, 0.86),
    ("appliance", ("fridge", "refrigerator", "washing machine", "oven", "холодильник", "стирал", "духов"), TicketPriority.MEDIUM, 0.84),
    ("access", ("key", "lock", "door", "access", "ключ", "замок", "дверь", "доступ"), TicketPriority.HIGH, 0.88),
)

GREETING_PHRASES = (
    "hi", "hello", "hey", "yo", "thanks", "thank you", "thx", "ty", "ok", "okay", "cool", "nice", "great",
    "good morning", "good evening", "good afternoon", "yes", "no", "please", "you're welcome",
    "привет", "здравствуйте", "здравствуй", "добрый день", "добрый вечер", "доброе утро", "хай",
    "спасибо", "благодарю", "пожалуйста", "ок", "окей", "хорошо", "понятно", "ясно", "ага", "угу", "да", "нет",
)


def classify(text: str) -> IntakeResult:
    normalized = f" {text.lower().strip()} "
    for category, keywords, priority, confidence in RULES:
        if any(keyword in normalized for keyword in keywords):
            return IntakeResult(category, priority, confidence, f"matched {category} keyword")
    return IntakeResult("other", TicketPriority.MEDIUM, 0.55, "no specific category rule matched")


def is_actionable_request(text: str) -> bool:
    """False for small talk (greetings/thanks/short acknowledgements) that shouldn't spawn a ticket."""
    normalized = f" {text.lower().strip()} "
    if any(keyword in normalized for _, keywords, _, _ in RULES for keyword in keywords):
        return True
    stripped = text.strip().lower().rstrip("!.,? ")
    if len(stripped) <= 3:
        return False
    return not any(stripped == phrase or stripped.startswith(phrase + " ") for phrase in GREETING_PHRASES)
