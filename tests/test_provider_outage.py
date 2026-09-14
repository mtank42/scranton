"""Provider outages surface as clean 502s, never raw 500s.

Born from the owner's report (2026-09-14): Mistral's free tier dropped
the commercial models, chat calls returned 429, and Tell Dwight showed
an Internal Server Error. The contract under test: SDK failures become
ProviderError at the adapter seam, services with a tailored message
translate it (the note is saved), and everything else lands on the
app-level 502 handler.
"""

import pytest
from fastapi import Request

from backend.app.adapters.llm.base import LLMProvider, ProviderError
from backend.app.adapters.llm.mistral import MistralProvider
from backend.app.api.deps import get_dwight_service
from backend.app.domain.models import (
    Entry,
    EntrySegment,
    ProcessingStatus,
    ValidationStatus,
)
from backend.app.services.dwight_service import DwightService
from tests.conftest import FakeVectorStore, ScriptedLLMProvider
from tests.test_dwight_service import TWO_SEGMENT_PROPOSAL


class DownLLMProvider(LLMProvider):
    """A provider whose backend is unreachable: every call raises."""

    def complete(self, messages: list[dict], *, model: str | None = None) -> str:
        """Simulate an outage on chat."""
        raise ProviderError("chat is down")

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Simulate an outage on embeddings."""
        raise ProviderError("embeddings are down")


class ChatOnlyProvider(ScriptedLLMProvider):
    """Chat answers fine, embeddings are down: the 2026-09-14 shape
    inverted, to hit the validation-time embed path."""

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Simulate an outage on embeddings only."""
        raise ProviderError("embeddings are down")


def override_dwight(app, llm) -> FakeVectorStore:
    """Route get_dwight_service to the given provider, real database."""
    store = FakeVectorStore()

    def fake_service(request: Request) -> DwightService:
        """Same wiring as the real dependency, the seam swapped."""
        return DwightService(
            llm=llm,
            session_factory=request.app.state.session_factory,
            vector_store=store,
        )

    app.dependency_overrides[get_dwight_service] = fake_service
    return store


# --- The adapter seam: vendor exceptions never cross it ---


class ExplodingSDK:
    """Stand-in for the mistralai client: every call raises SDK-side."""

    class chat:
        @staticmethod
        def complete(**kwargs):
            raise RuntimeError("429 rate limited (vendor exception)")

    class embeddings:
        @staticmethod
        def create(**kwargs):
            raise RuntimeError("429 rate limited (vendor exception)")


def test_mistral_adapter_translates_sdk_failures():
    """Whatever the SDK throws, the seam speaks ProviderError."""
    provider = MistralProvider(api_key="irrelevant")
    provider._client = ExplodingSDK()
    with pytest.raises(ProviderError):
        provider.complete([{"role": "user", "content": "hello"}])
    with pytest.raises(ProviderError):
        provider.embed(["hello"])


# --- Capture: the tailored message, and the note is SAFE ---


def test_capture_during_outage_is_502_and_the_note_is_saved(app, client):
    """The exact owner scenario: outage at capture time."""
    override_dwight(app, DownLLMProvider())

    response = client.post(
        "/api/v1/dwight/entries", json={"raw_content": "Note during the outage."}
    )

    assert response.status_code == 502
    assert "saved" in response.json()["detail"]
    with app.state.session_factory() as session:
        entry = session.query(Entry).order_by(Entry.id.desc()).first()
        assert entry.raw_content == "Note during the outage."
        assert entry.processing_status == ProcessingStatus.PENDING


# --- Validation embed: the app-level safety net ---


def test_validation_during_outage_is_502_and_nothing_is_decided(app, client):
    """Embeddings down at validation time: 502, the proposal stays
    proposed (retryable), nothing reaches the vector store."""
    llm = ChatOnlyProvider([TWO_SEGMENT_PROPOSAL])
    store = override_dwight(app, llm)
    captured = client.post(
        "/api/v1/dwight/entries", json={"raw_content": "Tables Thursday. Kevin."}
    ).json()
    segment_id = captured["segments"][0]["id"]

    response = client.post(
        f"/api/v1/dwight/segments/{segment_id}/validate", json={"status": "validated"}
    )

    assert response.status_code == 502
    assert "try again" in response.json()["detail"]
    assert store.upserted == []
    # The decision was NOT half-recorded: the segment is still proposed,
    # so the same click works once the provider is back.
    with app.state.session_factory() as session:
        segment = session.get(EntrySegment, segment_id)
        assert segment.validation_status == ValidationStatus.PROPOSED
