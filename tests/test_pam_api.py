"""The /api/v1/pam endpoint, with the service seams overridden."""

from fastapi import Request

from backend.app.adapters.vectorstore.base import Hit
from backend.app.api.deps import get_pam_service
from backend.app.services.pam_service import NO_MEMORY_ANSWER, PamService
from tests.conftest import FakeVectorStore, ScriptedLLMProvider


def override_service(app, hits: list[Hit], completions: list[str]) -> None:
    """Route get_pam_service to fakes, keeping the app's real database."""

    def fake_pam_service(request: Request) -> PamService:
        """Same wiring as the real dependency, fakes on the seams."""
        return PamService(
            llm=ScriptedLLMProvider(completions),
            session_factory=request.app.state.session_factory,
            vector_store=FakeVectorStore(hits=hits),
        )

    app.dependency_overrides[get_pam_service] = fake_pam_service


def test_query_returns_grounded_answer_with_sources(app, client):
    """Full HTTP flow: capture-free, seeded through Dwight is not required."""
    # Seed one segment directly through the app's own session factory.
    from backend.app.domain.models import DataType, Entry, EntrySegment, SourceType

    with app.state.session_factory() as session:
        entry = Entry(raw_content="raw", source_type=SourceType.NOTE)
        session.add(entry)
        session.flush()
        segment = EntrySegment(
            entry_id=entry.id,
            content="Kevin asked to talk: follow up on Monday.",
            segment_order=0,
            data_type=DataType.WARM,
            sensitivity_level=3,
        )
        session.add(segment)
        session.commit()
        segment_id = segment.id

    override_service(
        app,
        hits=[Hit(segment_id=segment_id, score=0.9, metadata={})],
        completions=["Kevin wanted to talk [1]."],
    )

    response = client.post("/api/v1/pam/query", json={"question": "What did Kevin want?"})

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == "Kevin wanted to talk [1]."
    assert len(body["sources"]) == 1
    assert body["sources"][0]["segment_id"] == segment_id
    assert body["sources"][0]["data_type"] == "warm"


def test_empty_memory_is_an_honest_200(app, client):
    """No relevant memory is a valid answer, not an error."""
    override_service(app, hits=[], completions=[])
    response = client.post("/api/v1/pam/query", json={"question": "Anything on Bergerac?"})
    assert response.status_code == 200
    assert response.json() == {"answer": NO_MEMORY_ANSWER, "sources": [], "summary": None}


def test_empty_question_is_rejected_by_validation(client):
    """FastAPI rejects an empty question before any processing."""
    response = client.post("/api/v1/pam/query", json={"question": ""})
    assert response.status_code == 422