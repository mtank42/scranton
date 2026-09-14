"""Mistral implementation of LLMProvider.

mistralai 2.x note: it is a namespace package, so the client import is
'from mistralai.client import Mistral' (not the 1.x style
'from mistralai import Mistral'). Chat messages are passed as plain
{"role": ..., "content": ...} dicts: the SDK validates them itself.
"""

from mistralai.client import Mistral

from backend.app.adapters.llm.base import LLMProvider, ProviderError


class MistralProvider(LLMProvider):
    """Mistral-backed provider for chat completion and embeddings.

    Default chat model: mistral-small-latest. Escalation path if routing
    quality falls short: small -> medium -> Gemini Flash, measured on the
    Tell Dwight pipeline (PRODUCT_ROADMAP.md section 9).
    """

    EMBED_MODEL = "mistral-embed"

    def __init__(self, api_key: str, default_model: str = "mistral-small-latest") -> None:
        """Store credentials and the default model: no network at construction.

        The SDK client is created lazily so building the app (or running
        offline tests) never requires a valid key.
        """
        self.api_key = api_key
        self.default_model = default_model
        self._client: Mistral | None = None

    @property
    def client(self) -> Mistral:
        """Create the SDK client on first use, then reuse it."""
        if self._client is None:
            self._client = Mistral(api_key=self.api_key)
        return self._client

    def complete(self, messages: list[dict], *, model: str | None = None) -> str:
        """Return the assistant reply for a chat-style list of messages.

        Any SDK failure (quota 429, bad key, network) becomes a
        ProviderError HERE: no vendor exception class ever crosses the
        seam - that is what kept a Mistral 429 surfacing as a raw 500
        until 2026-09-14.
        """
        try:
            response = self.client.chat.complete(
                model=model or self.default_model,
                messages=messages,
            )
        except Exception as exc:
            raise ProviderError(f"Mistral chat call failed: {exc}") from exc
        return response.choices[0].message.content

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return one embedding vector per input text, in the same order."""
        try:
            response = self.client.embeddings.create(
                model=self.EMBED_MODEL,
                inputs=texts,
            )
        except Exception as exc:
            raise ProviderError(f"Mistral embeddings call failed: {exc}") from exc
        return [item.embedding for item in response.data]
