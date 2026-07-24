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


def test_recent_entries_history(app, client):
    """The history strip: newest first, counters, limit and offset."""
    override_service(app, [TWO_SEGMENT_PROPOSAL, TWO_SEGMENT_PROPOSAL])
    first = client.post(
        "/api/v1/dwight/entries", json={"raw_content": "Older note about the tables."}
    ).json()
    second = client.post(
        "/api/v1/dwight/entries", json={"raw_content": "Newer note about Kevin."}
    ).json()
    client.post(
        f"/api/v1/dwight/segments/{second['segments'][0]['id']}/validate",
        json={"status": "validated"},
    )

    history = client.get("/api/v1/dwight/entries/recent?limit=5").json()

    assert [entry["id"] for entry in history] == [second["entry_id"], first["entry_id"]]
    assert history[0]["raw_content"] == "Newer note about Kevin."
    assert history[0]["segments_total"] == 2
    assert history[0]["segments_validated"] == 1
    assert history[1]["segments_validated"] == 0

    # The 'Show more' path pages past the first screen.
    paged = client.get("/api/v1/dwight/entries/recent?limit=5&offset=1").json()
    assert [entry["id"] for entry in paged] == [first["entry_id"]]


# --- The emitter doctrine (owner correction, 2026-07-19) ---
# Tell Dwight is the base of the product: EVERY team member files their
# daily report and feeds the shared memory. The session stamps the
# author, and only the author decides on their proposals.


def test_member_daily_report_is_stamped_and_validated_by_its_author(
    app, client, member_login
):
    """A member captures, sees THEIR thread, validates THEIR segment."""
    from backend.app.domain.models import Entry

    llm, store = override_service(app, [TWO_SEGMENT_PROPOSAL])
    member_client, member_id = member_login(name="Kelly")

    captured = member_client.post(
        "/api/v1/dwight/entries",
        # A claimed author is ignored: identity is proven, not declared.
        json={"raw_content": "Daily report: closed two tickets.", "submitted_by_id": 999},
    )
    assert captured.status_code == 201
    body = captured.json()
    with app.state.session_factory() as session:
        assert session.get(Entry, body["entry_id"]).submitted_by_id == member_id

    # Her history shows her note; the manager's thread stays empty.
    assert [e["id"] for e in member_client.get("/api/v1/dwight/entries/recent").json()] == [
        body["entry_id"]
    ]
    assert client.get("/api/v1/dwight/entries/recent").json() == []

    # She validates her own segment: the shared memory receives it.
    validated = member_client.post(
        f"/api/v1/dwight/segments/{body['segments'][0]['id']}/validate",
        json={"status": "validated"},
    )
    assert validated.status_code == 200
    assert len(store.upserted) == 1


def test_only_the_author_decides_not_even_the_manager(app, client, member_login):
    """Cross-emitter gestures are 403 in BOTH directions."""
    llm, store = override_service(app, [TWO_SEGMENT_PROPOSAL, TWO_SEGMENT_PROPOSAL])
    member_client, member_id = member_login(name="Ryan")

    hers = member_client.post(
        "/api/v1/dwight/entries", json={"raw_content": "My report."}
    ).json()
    his = client.post(
        "/api/v1/dwight/entries", json={"raw_content": "Manager note."}
    ).json()

    # The manager cannot decide on her proposal - the gate belongs to
    # whoever wrote the note (emitter validation, day-one doctrine).
    refused = client.post(
        f"/api/v1/dwight/segments/{hers['segments'][0]['id']}/validate",
        json={"status": "validated"},
    )
    assert refused.status_code == 403
    # And she cannot decide, rework or continue his.
    assert (
        member_client.post(
            f"/api/v1/dwight/segments/{his['segments'][0]['id']}/validate",
            json={"status": "validated"},
        ).status_code
        == 403
    )
    assert (
        member_client.post(
            f"/api/v1/dwight/segments/{his['segments'][0]['id']}/rework",
            json={"comment": "not mine"},
        ).status_code
        == 403
    )
    assert store.upserted == []
