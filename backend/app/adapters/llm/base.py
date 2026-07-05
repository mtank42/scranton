"""LLMProvider: the single seam for every model call.

No service ever imports a vendor SDK directly. Swapping Mistral for
Gemini (or a sovereign local model in V2) is a configuration change, and
unit tests run against a deterministic fake with zero network access.
"""

from abc import ABC, abstractmethod


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
