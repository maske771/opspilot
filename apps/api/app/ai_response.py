from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class GeneratedResponse:
    text: str
    provider: str
    confidence: float


class ResponseGenerator(Protocol):
    def generate(self, *, customer_message: str, category: str, priority: str) -> GeneratedResponse: ...


class LLMResponseGeneratorStub:
    """Future LLM integration point.

    This MVP intentionally does not call an external LLM. A real provider can be
    implemented here later without changing the API contract.
    """

    def generate(self, *, customer_message: str, category: str, priority: str) -> GeneratedResponse:
        raise RuntimeError("LLM provider is not configured")


class RuleBasedResponseGenerator:
    """Deterministic fallback used until a real LLM provider is configured."""

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


def get_response_generator() -> ResponseGenerator:
    """Return the current MVP provider.

    Keep this factory as the single future integration point for an LLM provider.
    """
    return RuleBasedResponseGenerator()


def generate_with_fallback(*, customer_message: str, category: str, priority: str) -> GeneratedResponse:
    """Generate a response without requiring an external LLM."""
    generator = get_response_generator()
    try:
        return generator.generate(
            customer_message=customer_message,
            category=category,
            priority=priority,
        )
    except Exception:
        return RuleBasedResponseGenerator().generate(
            customer_message=customer_message,
            category=category,
            priority=priority,
        )
