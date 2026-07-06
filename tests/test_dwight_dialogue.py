"""The Dwight dialogue: clarification replies and the rework loop."""

import json

import pytest

from backend.app.domain.models import Entry, EntrySegment, ProcessingStatus, ValidationStatus
from backend.app.services.dwight_service import (
    EntryNotFoundError,
    EntryNotPendingError,
    SegmentNotProposedError,
)
from tests.test_dwight_service import (
    CLARIFICATION_ANSWER,
    TWO_SEGMENT_PROPOSAL,
    capture_note,
    make_service,
    seed_member,
)

SINGLE_SEGMENT_PROPOSAL = json.dumps(
    {
        "clarification": None,
        "segments": [
            {
                "content": "Kevin finished the town hall tables ahead of schedule.",
                "data_type": "cold",
                "sensitivity_level": 1,
                "tags": [{"entity_type": "team_member", "entity_id": 1, "view_type": None, "confidence": 0.9}],
            }
        ],
    }
)


# --- clarification dialogue ---


def test_reply_resumes_a_pending_entry(session_factory):
    """Question, answer, segments: the thread ends on a complete entry."""
    seed_member(session_factory)
    service, llm, store = make_service(
        session_factory, [CLARIFICATION_ANSWER, TWO_SEGMENT_PROPOSAL]
    )
    captured = capture_note(service, "I did it")
    assert captured.clarification

    result = service.reply(captured.entry_id, "I closed the town hall deal")

    assert result.clarification is None
    assert result.processing_status == ProcessingStatus.COMPLETE
    assert len(result.segments) == 2
    # The answer went to the model inside the reprocessing context...
    reply_prompt = llm.complete_calls[1][-1]["content"]
    assert "I closed the town hall deal" in reply_prompt
    assert "Additional context from the manager" in reply_prompt
    # ...but the raw entry itself is untouched (immutability).
    with session_factory() as session:
        assert session.get(Entry, captured.entry_id).raw_content == "I did it"


def test_reply_can_loop_on_a_second_clarification(session_factory):
    """Dwight may ask again: the entry simply stays pending."""
    service, llm, store = make_service(
        session_factory, [CLARIFICATION_ANSWER, CLARIFICATION_ANSWER]
    )
    captured = capture_note(service, "things happened")

    result = service.reply(captured.entry_id, "with the client")

    assert result.clarification
    assert result.processing_status == ProcessingStatus.PENDING


def test_reply_rejects_wrong_targets(session_factory):
    """404 material for a missing entry, 409 material for a decided one."""
    seed_member(session_factory)
    service, llm, store = make_service(session_factory, [TWO_SEGMENT_PROPOSAL])
    captured = capture_note(service)  # completes immediately

    with pytest.raises(EntryNotFoundError):
        service.reply(999, "hello")
    with pytest.raises(EntryNotPendingError):
        service.reply(captured.entry_id, "hello")


# --- rework loop ---


def test_rework_replaces_the_proposal_and_keeps_the_audit_trail(session_factory):
    """Old segment rejected, corrected one proposed at the same position."""
    seed_member(session_factory)
    service, llm, store = make_service(
        session_factory, [TWO_SEGMENT_PROPOSAL, SINGLE_SEGMENT_PROPOSAL]
    )
    captured = capture_note(service)
    target = captured.segments[0]

    replacement = service.rework(target.id, "This is about Kevin, not the delivery")

    assert replacement.id != target.id
    assert replacement.segment_order == target.segment_order
    assert replacement.validation_status == ValidationStatus.PROPOSED
    assert "Kevin finished" in replacement.content
    # The comment and the rejected text both reached the model.
    rework_prompt = llm.complete_calls[1][-1]["content"]
    assert "This is about Kevin, not the delivery" in rework_prompt
    assert target.content in rework_prompt
    with session_factory() as session:
        old = session.get(EntrySegment, target.id)
        assert old.validation_status == ValidationStatus.REJECTED
        # Audit trail: 2 original + 1 replacement rows on the entry.
        assert session.query(EntrySegment).count() == 3


def test_rework_only_applies_to_proposals(session_factory):
    """A decided segment cannot re-enter the loop."""
    seed_member(session_factory)
    service, llm, store = make_service(session_factory, [TWO_SEGMENT_PROPOSAL])
    captured = capture_note(service)
    decided = service.validate_segment(captured.segments[0].id, ValidationStatus.VALIDATED)

    with pytest.raises(SegmentNotProposedError):
        service.rework(decided.id, "too late")


def test_rework_loop_can_run_twice_then_validate(session_factory):
    """Rework of a rework works; validating the survivor embeds it."""
    seed_member(session_factory)
    service, llm, store = make_service(
        session_factory,
        [TWO_SEGMENT_PROPOSAL, SINGLE_SEGMENT_PROPOSAL, SINGLE_SEGMENT_PROPOSAL],
    )
    captured = capture_note(service)
    first = service.rework(captured.segments[0].id, "wrong")
    second = service.rework(first.id, "still wrong")

    validated = service.validate_segment(second.id, ValidationStatus.VALIDATED)

    assert validated.validation_status == ValidationStatus.VALIDATED
    assert [vector.segment_id for vector in store.upserted] == [second.id]


# --- HTTP surface ---


def test_reply_and_rework_endpoints(app, client):
    """Status mapping: 409 on a decided entry, 404 on ghosts."""
    from fastapi import Request

    from backend.app.api.deps import get_dwight_service
    from backend.app.services.dwight_service import DwightService
    from tests.conftest import FakeVectorStore, ScriptedLLMProvider

    llm = ScriptedLLMProvider([TWO_SEGMENT_PROPOSAL])

    def fake_service(request: Request) -> DwightService:
        """Real wiring on the app database, scripted model."""
        return DwightService(
            llm=llm,
            session_factory=request.app.state.session_factory,
            vector_store=FakeVectorStore(),
        )

    app.dependency_overrides[get_dwight_service] = fake_service
    captured = client.post("/api/v1/dwight/entries", json={"raw_content": "note"}).json()

    reply = client.post(
        f"/api/v1/dwight/entries/{captured['entry_id']}/reply", json={"message": "more"}
    )
    assert reply.status_code == 409  # entry completed, nothing to clarify
    assert client.post("/api/v1/dwight/entries/999/reply", json={"message": "x"}).status_code == 404
    assert client.post("/api/v1/dwight/segments/999/rework", json={"comment": "x"}).status_code == 404