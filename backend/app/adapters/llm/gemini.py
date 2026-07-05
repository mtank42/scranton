"""Gemini implementation of LLMProvider: stub, fallback provider.

Gemini Flash is the planned fallback if Mistral routing or extraction
quality is short for Tell Dwight (PRODUCT_ROADMAP.md section 8). Keeping
the class here from day one proves the provider seam is real: adding a
provider is one file plus one factory branch, never a refactor.
"""

from backend.app.adapters.llm.base import LLMProvider


class GeminiProvider(LLMProvider):
    """Gemini-backed provider. Implemented only if quality demands it."""

    def __init__(self, api_key: str, default_model: str = "gemini-flash-latest") -> None:
        """Store credentials and the default model: no network at construction."""
        self.api_key = api_key
        self.default_model = default_model

    def complete(self, messages: list[dict], *, model: str | None = None) -> str:
        """Not implemented: activated only if Mistral quality falls short."""
        raise NotImplementedError("GeminiProvider is a fallback: implement when needed.")

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Not implemented: activated only if Mistral quality falls short."""
        raise NotImplementedError("GeminiProvider is a fallback: implement when needed.")
