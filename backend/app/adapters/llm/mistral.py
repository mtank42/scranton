"""Mistral implementation of LLMProvider: stub until M1 (Tell Dwight).

Note for M1: mistralai 2.x is a namespace package, so the client import
is 'from mistralai.client import Mistral' (not the 1.x style
'from mistralai import Mistral'). Default model: mistral-small-latest;
escalate small -> medium -> Gemini Flash empirically once Tell Dwight
makes routing quality measurable (PRODUCT_ROADMAP.md section 9).
"""

from backend.app.adapters.llm.base import LLMProvider


class MistralProvider(LLMProvider):
    """Mistral-backed provider.

    Real calls land in M1. The shape is fixed now so nothing else in the
    codebase ever depends on the vendor SDK directly.
    """

    def __init__(self, api_key: str, default_model: str = "mistral-small-latest") -> None:
        """Store credentials and the default model: no network at construction."""
        self.api_key = api_key
        self.default_model = default_model

    def complete(self, messages: list[dict], *, model: str | None = None) -> str:
        """Not implemented yet: the Tell Dwight pipeline (M1) brings it."""
        raise NotImplementedError("MistralProvider.complete lands in M1 (Tell Dwight).")

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Not implemented yet: needed from M1 on (segment embedding)."""
        raise NotImplementedError("MistralProvider.embed lands in M1 (Tell Dwight).")
