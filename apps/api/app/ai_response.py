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
    """Safe deterministic baseline used until an external LLM provider is configured."""

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
    # Provider selection is intentionally isolated so an LLM can be added without changing the API contract.
    return RuleBasedResponseGenerator()
