"""The validated tables: schema creation and a full capture roundtrip."""

from sqlalchemy import inspect
from sqlalchemy.orm import Session

from backend.app.db.init_db import init_db
from backend.app.domain.models import (
    DataType,
    EntityType,
    Entry,
    EntrySegment,
    ProcessingStatus,
    ProposedBy,
    SegmentTag,
    SourceType,
    TeamMember,
    ValidationStatus,
)

EXPECTED_TABLES = {
    "team_members",
    "entries",
    "entry_segments",
    "segment_tags",
    "clients",
    "projects",
    "stakeholders",
    "mood_checkins",
    # Added in the dedicated data model session (2026-07-08).
    "handover_validations",
    # The documentary corpus, added in the Darryl session (2026-07-15).
    "documents",
    "document_chunks",
    "document_tags",
    # The manager's clean notebook, added in the document-editing
    # session (2026-07-16).
    "edited_documents",
    # Login accounts and browser sessions, added in the identity
    # session (2026-07-18, the privacy-first pivot).
    "users",
    "sessions",
}


def test_init_db_creates_the_validated_tables(engine):
    """init_db materializes exactly the validated data model: no more, no less."""
    init_db(engine)
    assert set(inspect(engine).get_table_names()) == EXPECTED_TABLES


def test_capture_chain_roundtrip(engine):
    """entries -> entry_segments -> segment_tags: the Tell Dwight backbone.

    The scenario is the pitch itself: Pascal notes that Kevin wants to
    talk. The note is stored raw, one warm segment is proposed, and the
    segment is routed to Kevin's team member file.
    """
    init_db(engine)
    with Session(engine) as session:
        member = TeamMember(full_name="Kevin", role="Senior carpenter")
        entry = Entry(
            raw_content="Kevin has something to tell me, call back Monday.",
            source_type=SourceType.NOTE,
        )
        session.add_all([member, entry])
        session.flush()

        segment = EntrySegment(
            entry_id=entry.id,
            content="Kevin asked to talk: follow up on Monday.",
            segment_order=0,
            data_type=DataType.WARM,
            sensitivity_level=3,
        )
        session.add(segment)
        session.flush()

        session.add(
            SegmentTag(
                segment_id=segment.id,
                entity_type=EntityType.TEAM_MEMBER,
                entity_id=member.id,
                proposed_by=ProposedBy.DWIGHT,
                confidence=0.9,
            )
        )
        session.commit()

        stored = session.get(Entry, entry.id)
        assert stored.processing_status == ProcessingStatus.PENDING
        assert stored.segments[0].validation_status == ValidationStatus.PROPOSED
        assert stored.segments[0].data_type == DataType.WARM
        assert stored.segments[0].tags[0].validated is False
