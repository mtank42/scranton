"""The Tell Dwight pipeline, tested against a scripted model.

Every test scripts what 'the model' answers, then asserts on what the
pipeline persisted, indexed, or refused. No network anywhere.
"""

import json

import pytest
from sqlalchemy.orm import Session

from backend.app.domain.models import (
    DataType,
    Entry,
    EntrySegment,
    ProcessingStatus,
    ProposedBy,
    TeamMember,
    ValidationStatus,
)
from backend.app.domain.schemas import EntryCreate
from backend.app.services.dwight_service import (
    DwightProcessingError,
    DwightService,
    SegmentNotFoundError,
    extract_json,
)
from tests.conftest import FakeVectorStore, ScriptedLLMProvider

# A realistic two-segment proposal: one cold fact routed to a commitment
# view, one warm observation routed to a team member.
TWO_SEGMENT_PROPOSAL = json.dumps(
    {
        "clarification": None,
        "segments": [
            {
                "content": "Delivery of the town hall tables confirmed for Thursday.",
                "data_type": "cold",
                "sensitivity_level": 1,
                "tags": [{"entity_type": "view", "entity_id": None, "view_type": "commitment", "confidence": 0.85}],
            },
            {
                "content": "Kevin asked to talk: follow up on Monday.",
                "data_type": "warm",
                "sensitivity_level": 3,
                "tags": [{"entity_type": "team_member", "entity_id": 1, "view_type": None, "confidence": 0.9}],
            },
        ],
    }
)

CLARIFICATION_ANSWER = json.dumps(
    {"clarification": "Which project is this note about?", "segments": []}
)


def make_service(session_factory, completions: list[str]) -> tuple[DwightService, ScriptedLLMProvider, FakeVectorStore]:
    """Assemble a DwightService on scripted fakes, returning all three."""
    llm = ScriptedLLMProvider(completions)
    store = FakeVectorStore()
    return DwightService(llm=llm, session_factory=session_factory, vector_store=store), llm, store


def seed_member(session_factory) -> int:
    """Insert one team member and return its id (for entity tags)."""
    with session_factory() as session:
        member = TeamMember(full_name="Kevin", role="Senior carpenter")
        session.add(member)
        session.commit()
        return member.id


def capture_note(service: DwightService, text: str = "Tables delivered Thursday. Kevin wants to talk."):
    """Run one note through the pipeline with a default payload."""
    return service.capture(EntryCreate(raw_content=text))


def test_capture_persists_segments_and_tags(session_factory):
    """Nominal path: raw entry stored, segments and tags proposed."""
    seed_member(session_factory)
    service, llm, store = make_service(session_factory, [TWO_SEGMENT_PROPOSAL])

    result = capture_note(service)

    assert result.processing_status == ProcessingStatus.COMPLETE
    assert result.clarification is None
    assert len(result.segments) == 2
    warm = result.segments[1]
    assert warm.data_type == DataType.WARM
    assert warm.validation_status == ValidationStatus.PROPOSED
    assert warm.tags[0].proposed_by == ProposedBy.DWIGHT
    assert warm.tags[0].validated is False
    # Nothing is indexed at capture time: validation is the gate.
    assert store.upserted == []


def test_raw_entry_is_persisted_before_the_model_answers(session_factory):
    """Even if the LLM fails hard, the note itself is never lost."""
    service, llm, store = make_service(session_factory, ["not json", "still not json"])

    with pytest.raises(DwightProcessingError):
        capture_note(service)

    with session_factory() as session:
        entries = session.query(Entry).all()
        assert len(entries) == 1
        assert entries[0].processing_status == ProcessingStatus.PENDING
        assert session.query(EntrySegment).count() == 0


def test_vague_note_returns_clarification_and_stays_pending(session_factory):
    """Too vague: one question back, entry pending, nothing else persisted."""
    service, llm, store = make_service(session_factory, [CLARIFICATION_ANSWER])

    result = capture_note(service, "things went ok I guess")

    assert result.clarification == "Which project is this note about?"
    assert result.processing_status == ProcessingStatus.PENDING
    assert result.segments == []


def test_invalid_json_is_retried_once(session_factory):
    """First malformed answer triggers exactly one retry with a reminder."""
    seed_member(session_factory)
    service, llm, store = make_service(
        session_factory, ["I think the segments are...", TWO_SEGMENT_PROPOSAL]
    )

    result = capture_note(service)

    assert len(result.segments) == 2
    assert len(llm.complete_calls) == 2
    # The retry carries the failed answer back to the model as context.
    retry_messages = llm.complete_calls[1]
    assert retry_messages[-2]["role"] == "assistant"
    assert "valid JSON" in retry_messages[-1]["content"]


def test_markdown_fences_are_tolerated(session_factory):
    """A ```json fenced answer parses without burning the retry."""
    fenced = f"```json\n{TWO_SEGMENT_PROPOSAL}\n```"
    assert extract_json(fenced) == json.loads(TWO_SEGMENT_PROPOSAL)


def test_validation_embeds_only_validated_segments(session_factory):
    """VALIDATED -> embedded with flattened metadata; REJECTED -> kept out."""
    seed_member(session_factory)
    service, llm, store = make_service(session_factory, [TWO_SEGMENT_PROPOSAL])
    result = capture_note(service)
    cold, warm = result.segments

    validated = service.validate_segment(warm.id, ValidationStatus.VALIDATED)
    rejected = service.validate_segment(cold.id, ValidationStatus.REJECTED)

    assert validated.validation_status == ValidationStatus.VALIDATED
    assert validated.tags[0].validated is True
    assert rejected.validation_status == ValidationStatus.REJECTED
    assert rejected.tags[0].validated is False
    # Only the validated segment reached the vector store.
    assert len(store.upserted) == 1
    vector = store.upserted[0]
    assert vector.segment_id == warm.id
    assert vector.metadata["data_type"] == "warm"
    assert vector.metadata["sensitivity_level"] == 3
    assert vector.metadata["team_member_1"] is True
    assert llm.embed_calls == [[warm.content]]


def test_validating_a_missing_segment_fails_cleanly(session_factory):
    """Unknown id raises the domain error the API maps to 404."""
    service, llm, store = make_service(session_factory, [])
    with pytest.raises(SegmentNotFoundError):
        service.validate_segment(999, ValidationStatus.VALIDATED)


def test_profile_suggestions_are_resolved_and_filtered(session_factory):
    """Known member: name attached. Unknown member: silently dropped.

    Suggestions are transient (consent-preserving): nothing lands in the
    profile without an explicit manager action on the team endpoints.
    """
    member_id = seed_member(session_factory)
    proposal = json.dumps(
        {
            "clarification": None,
            "segments": [
                {
                    "content": "Kevin was born on February 11 and loves New Order.",
                    "data_type": "warm",
                    "sensitivity_level": 3,
                    "tags": [{"entity_type": "team_member", "entity_id": member_id, "view_type": None, "confidence": 0.9}],
                }
            ],
            "profile_suggestions": [
                {"team_member_id": member_id, "text": "Fan of New Order.", "birthday": "1985-02-11"},
                {"team_member_id": 999, "text": "Ghost fact.", "birthday": None},
            ],
        }
    )
    service, llm, store = make_service(session_factory, [proposal])

    result = capture_note(service, "kevin est ne le 11 fevrier, fan de new order")

    assert len(result.profile_suggestions) == 1
    suggestion = result.profile_suggestions[0]
    assert suggestion.member_name == "Kevin"
    assert suggestion.text == "Fan of New Order."
    # A birthday is a day, not an age: whatever year the model emitted
    # (1985 here - real or invented, it cannot tell) is erased.
    assert str(suggestion.birthday) == "2000-02-11"
    # The suggestion is NOT persisted anywhere: profile untouched.
    from backend.app.domain.models import TeamMember

    with session_factory() as session:
        assert session.get(TeamMember, member_id).personal_profile is None


def test_routing_context_lists_known_entities(session_factory):
    """The prompt receives the actual roster, with ids the model may use."""
    member_id = seed_member(session_factory)
    service, llm, store = make_service(session_factory, [TWO_SEGMENT_PROPOSAL])

    capture_note(service)

    user_prompt = llm.complete_calls[0][-1]["content"]
    assert f"id={member_id} Kevin" in user_prompt
    assert "clients: (none)" in user_prompt
