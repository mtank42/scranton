"""The /api/v1/dwight endpoints, with the service seams overridden.

These tests exercise the HTTP layer (status codes, payload shapes) on
top of scripted fakes injected through FastAPI dependency overrides.
"""

import json

from fastapi import Request

from backend.app.api.deps import get_dwight_service
from backend.app.services.dwight_service import DwightService
from tests.conftest import FakeVectorStore, ScriptedLLMProvider
from tests.test_dwight_service import TWO_SEGMENT_PROPOSAL

INVALID_TWICE = ["not json", "still not json"]


def override_service(app, completions: list[str]) -> tuple[ScriptedLLMProvider, FakeVectorStore]:
    """Route get_dwight_service to fakes, keeping the app's real database."""
    llm = ScriptedLLMProvider(completions)
    store = FakeVectorStore()

    def fake_dwight_service(request: Request) -> DwightService:
        """Same wiring as the real dependency, fakes on the seams."""
        return DwightService(
            llm=llm,
            session_factory=request.app.state.session_factory,
            vector_store=store,
        )

    app.dependency_overrides[get_dwight_service] = fake_dwight_service
    return llm, store


def test_capture_returns_201_with_proposal(app, client):
    """A note comes back as a persisted entry with proposed segments."""
    override_service(app, [TWO_SEGMENT_PROPOSAL])

    response = client.post(
        "/api/v1/dwight/entries",
        json={"raw_content": "Tables delivered Thursday. Kevin wants to talk."},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["processing_status"] == "complete"
    assert len(body["segments"]) == 2
    assert body["segments"][1]["data_type"] == "warm"
    assert body["segments"][1]["tags"][0]["proposed_by"] == "dwight"


def test_capture_then_validate_roundtrip(app, client):
    """The full manager flow: capture, then validate one segment."""
    llm, store = override_service(app, [TWO_SEGMENT_PROPOSAL])
    captured = client.post(
        "/api/v1/dwight/entries", json={"raw_content": "Tables Thursday. Kevin."}
    ).json()
    segment_id = captured["segments"][1]["id"]

    response = client.post(
        f"/api/v1/dwight/segments/{segment_id}/validate", json={"status": "validated"}
    )

    assert response.status_code == 200
    assert response.json()["validation_status"] == "validated"
    assert [vector.segment_id for vector in store.upserted] == [segment_id]


def test_empty_note_is_rejected_by_validation(client):
    """FastAPI rejects an empty raw_content before any processing."""
    response = client.post("/api/v1/dwight/entries", json={"raw_content": ""})
    assert response.status_code == 422


def test_model_failure_maps_to_502(app, client):
    """Two malformed model answers surface as a gateway error, not a 500."""
    override_service(app, INVALID_TWICE)
    response = client.post("/api/v1/dwight/entries", json={"raw_content": "note"})
    assert response.status_code == 502
    assert "pending" in response.json()["detail"]


def test_validating_unknown_segment_returns_404(app, client):
    """A decision on a segment that does not exist is a clean 404."""
    override_service(app, [])
    response = client.post("/api/v1/dwight/segments/999/validate", json={"status": "rejected"})
    assert response.status_code == 404
