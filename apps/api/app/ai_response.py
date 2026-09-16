import os
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class GeneratedResponse:
    text: str
    provider: str
    confidence: float


class ResponseGenerator(Protocol):
    def generate(self, *, customer_message: str, category: str, priority: str) -> GeneratedResponse: ...


class RuleBasedResponseGenerator:
    """Safe deterministic fallback used when an LLM is unavailable or not configured."""

    def generate(self, *, customer_message: str, category: str, priority: str) -> GeneratedResponse:
        if priority == "critical":
            text = "We received your urgent request and have marked it as critical. Our team will review it as soon as possible."
        elif category == "plumbing":
            text = "We received your plumbing request. Please tell us whether water is actively leaking and, if possible, where the leak is located."
        elif category == "electrical":
            text = "We received your electrical request. If there is smoke, fire, sparking, or an immediate safety risk, move to a safe location and contact emergency services."
        else:
            text = "We received your request. Our team has registered it and will review the details shortly."
        return GeneratedResponse(text=text, provider="rule-based", confidence=0.82)


class OpenAIResponseGenerator:
    """OpenAI Responses API provider. The caller falls back if this provider fails."""

    def __init__(self) -> None:
        from openai import OpenAI

        self.client = OpenAI(
            api_key=os.environ["OPENAI_API_KEY"],
            timeout=float(os.getenv("OPENAI_TIMEOUT_SECONDS", "15")),
        )
        self.model = os.getenv("OPENAI_MODEL", "gpt-5.6-luna")

    def generate(self, *, customer_message: str, category: str, priority: str) -> GeneratedResponse:
        response = self.client.responses.create(
            model=self.model,
            instructions=(
                "You are OpsPilot, a property-management support assistant. "
                "Draft a concise customer-facing reply based only on the supplied message and classification. "
                "Do not invent facts, prices, appointments, names, policies, or completed actions. "
                "For critical safety issues, recommend immediate safety measures and appropriate emergency services. "
                "Return only the reply text, with no markdown heading or analysis."
            ),
            input=(
                f"Customer message:\n{customer_message}\n\n"
                f"Category: {category}\n"
                f"Priority: {priority}"
            ),
        )
        text = response.output_text.strip()
        if not text:
            raise RuntimeError("LLM returned an empty response")
        return GeneratedResponse(text=text, provider="openai", confidence=0.90)


def get_response_generator() -> ResponseGenerator:
    if os.getenv("OPENAI_API_KEY"):
        try:
            return OpenAIResponseGenerator()
        except Exception:
            pass
    return RuleBasedResponseGenerator()


def generate_with_fallback(*, customer_message: str, category: str, priority: str) -> GeneratedResponse:
    """Generate with the configured LLM and fall back to deterministic text on provider errors."""
    fallback = RuleBasedResponseGenerator()
    generator = get_response_generator()
    if isinstance(generator, RuleBasedResponseGenerator):
        return generator.generate(
            customer_message=customer_message,
            category=category,
            priority=priority,
        )
    try:
        return generator.generate(
            customer_message=customer_message,
            category=category,
            priority=priority,
        )
    except Exception:
        return fallback.generate(
            customer_message=customer_message,
            category=category,
            priority=priority,
        )
