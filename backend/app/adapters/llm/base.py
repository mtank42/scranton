"""LLMProvider: the single seam for every model call.

No service ever imports a vendor SDK directly. Swapping Mistral for
Gemini (or a sovereign local model in V2) is a configuration change, and
unit tests run against a deterministic fake with zero network access.
"""

from abc import ABC, abstractmethod


class ProviderError(Exception):
    """The provider itself failed us: outage, quota, auth, network.

    Adapters translate their SDK exceptions into this ONE type at the
    seam, so no vendor exception class ever leaks into a service. The
    app maps it to a clean 502 (main.py exception handler); before it
    existed, a Mistral 429 surfaced as a raw 500 (owner report,
    2026-09-14: the free tier had dropped the commercial models).
    Distinct from LLMContractError on purpose: a contract error means
    the model ANSWERED badly, a provider error means it never
    answered - retrying later is the fix, not rewording.
    """


class LLMProvider(ABC):
    """Abstract contract for chat completion and text embedding."""

    @abstractmethod
    def complete(self, messages: list[dict], *, model: str | None = None) -> str:
        """Return the assistant reply for a chat-style list of messages.

        messages follows the common chat shape:
        [{"role": "user", "content": "..."}]. model overrides the provider
        default, so a task can escalate (small vs medium) without a new
        provider instance.
        """

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return one embedding vector per input text, in the same order."""
