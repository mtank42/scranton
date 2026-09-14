"""Ollama implementation of LLMProvider: local open-weights inference.

The maximum-sovereignty path (V2 exploration, 2026-07-09): nothing ever
leaves the machine. Talks to a local Ollama server over its native HTTP
API using the standard library only - a local adapter should not pull in
a network dependency.
"""

import json
import urllib.error
import urllib.request

from backend.app.adapters.llm.base import LLMProvider, ProviderError

# Local 7B-class inference is slow on long prompts: generous on purpose.
TIMEOUT_SECONDS = 300


class OllamaProvider(LLMProvider):
    """LLMProvider backed by a local Ollama server.

    Default chat model: mistral (7B open weights) - the smallest member
    of the same family the API path uses, so A/B comparisons stay
    within one model lineage.
    """

    EMBED_MODEL = "nomic-embed-text"

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        default_model: str = "mistral",
    ) -> None:
        """Store the endpoint and model: no connection until the first call."""
        self.base_url = base_url.rstrip("/")
        self.default_model = default_model

    def _post(self, path: str, payload: dict) -> dict:
        """One JSON round-trip to the local server.

        The single choke point: a server that is down, times out or
        errors becomes a ProviderError at the seam, like every other
        adapter.
        """
        request = urllib.request.Request(
            f"{self.base_url}{path}",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
                return json.loads(response.read())
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise ProviderError(f"Ollama call failed: {exc}") from exc

    def complete(self, messages: list[dict], *, model: str | None = None) -> str:
        """Return the assistant reply for a chat-style list of messages."""
        data = self._post(
            "/api/chat",
            {
                "model": model or self.default_model,
                "messages": messages,
                "stream": False,
            },
        )
        return data["message"]["content"]

    def embed(self, texts: list[str]) -> list[list[float]]:
        """One embedding vector per input text, in the same order.

        Chat models do not embed: requires a pulled embedding model
        (ollama pull nomic-embed-text). Fails loudly otherwise.
        """
        data = self._post("/api/embed", {"model": self.EMBED_MODEL, "input": texts})
        return data["embeddings"]
