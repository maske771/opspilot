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


def classify(text: str) -> IntakeResult:
    normalized = f" {text.lower().strip()} "
    for category, keywords, priority, confidence in RULES:
        if any(keyword in normalized for keyword in keywords):
            return IntakeResult(category, priority, confidence, f"matched {category} keyword")
    return IntakeResult("other", TicketPriority.MEDIUM, 0.55, "no specific category rule matched")
