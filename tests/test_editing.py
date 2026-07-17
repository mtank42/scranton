"""The document-editing engine: save, delta, revise, diff, corpus entry.

Owner arbitrations under test (2026-07-16): the saved document never
changes on its own; the delta is deterministic SQL; Dwight is a pure
reviser whose changes come back as a COMPUTED diff; client/project
documents feed Darryl's corpus while person-targeted ones never do;
a Drive sync never touches Scranton-born documents.
"""

import json
from datetime import datetime, timedelta

import pytest

from backend.app.domain.models import (
    Client,
    Document,
    Entry,
    EntrySegment,
    EntityType,
    SegmentTag,
    SourceType,
    TeamMember,
    DataType,
    ProposedBy,
    ValidationStatus,
)
from backend.app.domain.schemas import EditedDocumentCreate, EditedDocumentUpdate
from backend.app.services.darryl_service import DarrylService
from backend.app.services.editing_service import (
    EditedDocumentNotFoundError,
    EditingService,
    diff_spans,
)
from tests.conftest import FakeVectorStore, ScriptedLLMProvider


class EmptySource:
    """A document source with nothing in it (sync tests)."""

    def fetch(self):
        """No documents: the connector's folder is empty."""
        return []


def build_engine(session_factory, completions=None):
    """Wire an EditingService (and its Darryl) on scripted seams."""
    llm = ScriptedLLMProvider(completions or [])
    store = FakeVectorStore()
    darryl = DarrylService(
        source=EmptySource(),
        llm=llm,
        session_factory=session_factory,
        vector_store=store,
    )
    engine = EditingService(llm=llm, session_factory=session_factory, darryl=darryl)
    return engine, llm, store


@pytest.fixture
def ryan(session_factory):
    """A team member with one validated segment and its entry."""
    with session_factory() as session:
        member = TeamMember(full_name="Ryan", role="Sales")
        client = Client(name="Prince Family Paper")
        entry = Entry(raw_content="raw", source_type=SourceType.NOTE)
        session.add_all([member, client, entry])
        session.flush()
        ids = {"member_id": member.id, "client_id": client.id, "entry_id": entry.id}
        session.commit()
        return ids


def add_validated_segment(session_factory, entry_id, entity_type, entity_id, content, when):
    """Plant one validated, tagged segment at a chosen moment."""
    with session_factory() as session:
        segment = EntrySegment(
            entry_id=entry_id,
            content=content,
            segment_order=0,
            data_type=DataType.COLD,
            sensitivity_level=1,
            validation_status=ValidationStatus.VALIDATED,
            created_at=when,
        )
        session.add(segment)
        session.flush()
        session.add(
            SegmentTag(
                segment_id=segment.id,
                entity_type=entity_type,
                entity_id=entity_id,
                proposed_by=ProposedBy.DWIGHT,
                confidence=1.0,
                validated=True,
            )
        )
        session.commit()
        return segment.id


# Relative to the REAL clock on purpose: mark_reviewed stamps now, so
# fixed 'future' dates would silently invert every comparison.
GENERATED_AT = datetime.utcnow() - timedelta(days=7)


def create_payload(ryan, **overrides):
    """A 1:1 brief creation payload, overridable per test."""
    values = dict(
        title="Team Member - Ryan",
        template_key="team_member_file",
        target_entity_type=EntityType.TEAM_MEMBER,
        target_entity_id=ryan["member_id"],
        content_md="## Wins\n\nPrince Family Paper renewal signed.",
        generated_at=GENERATED_AT,
    )
    values.update(overrides)
    return EditedDocumentCreate(**values)


# --- the diff: computed, lossless, never self-reported ---


def test_diff_spans_rebuild_both_sides():
    """equal+insert rebuilds 'after', equal+delete rebuilds 'before'."""
    before = "Keep this. Remove that point. Keep the end."
    after = "Keep this. Add a brand new point. Keep the end."
    spans = diff_spans(before, after)
    rebuilt_after = "".join(s.text for s in spans if s.op in ("equal", "insert"))
    rebuilt_before = "".join(s.text for s in spans if s.op in ("equal", "delete"))
    assert rebuilt_after == after
    assert rebuilt_before == before
    assert any(s.op == "insert" for s in spans)
    assert any(s.op == "delete" for s in spans)


def test_diff_spans_identical_text_is_one_equal_span():
    """No change means no highlight: a single equal span."""
    text = "## Wins\n\nNothing changed here."
    assert [s.op for s in diff_spans(text, text)] == ["equal"]


# --- persistence and the bookmark ---


def test_create_starts_the_bookmark_at_generation(session_factory, ryan):
    """memory_reviewed_at = generated_at: news counts from the generation."""
    engine, _, _ = build_engine(session_factory)
    doc = engine.create(create_payload(ryan))
    assert doc.memory_reviewed_at == doc.generated_at
    assert doc.news_count == 0


def test_delta_presents_only_newer_validated_segments(session_factory, ryan):
    """The delta: validated, about the target, newer than the bookmark."""
    engine, _, _ = build_engine(session_factory)
    doc = engine.create(create_payload(ryan))
    generated = GENERATED_AT
    add_validated_segment(
        session_factory, ryan["entry_id"], EntityType.TEAM_MEMBER, ryan["member_id"],
        "Old news, already in the brief.", generated - timedelta(days=2),
    )
    fresh_id = add_validated_segment(
        session_factory, ryan["entry_id"], EntityType.TEAM_MEMBER, ryan["member_id"],
        "Q3 reporting is up to date.", generated + timedelta(days=3),
    )
    add_validated_segment(
        session_factory, ryan["entry_id"], EntityType.CLIENT, ryan["client_id"],
        "About someone else's subject.", generated + timedelta(days=3),
    )
    delta = engine.delta(doc.id)
    assert [s.segment_id for s in delta.segments] == [fresh_id]
    assert engine.get(doc.id).news_count == 1


def test_mark_reviewed_dismisses_for_good(session_factory, ryan):
    """The bookmark advances; the segment stays in the memory tables."""
    engine, _, _ = build_engine(session_factory)
    doc = engine.create(create_payload(ryan))
    # In the past relative to the REAL clock: mark_reviewed stamps now,
    # and a 'future' segment would legitimately still count as news.
    add_validated_segment(
        session_factory, ryan["entry_id"], EntityType.TEAM_MEMBER, ryan["member_id"],
        "News to dismiss.", datetime.utcnow() - timedelta(hours=1),
    )
    assert engine.get(doc.id).news_count == 1
    reviewed = engine.mark_reviewed(doc.id)
    assert reviewed.news_count == 0
    assert engine.delta(doc.id).segments == []


def test_save_updates_the_last_state_only(session_factory, ryan):
    """No version history (owner arbitration): one clean notebook."""
    engine, _, _ = build_engine(session_factory)
    doc = engine.create(create_payload(ryan))
    saved = engine.save(doc.id, EditedDocumentUpdate(content_md="## Wins\n\nRewritten."))
    assert saved.content_md == "## Wins\n\nRewritten."
    assert engine.get(doc.id).content_md == "## Wins\n\nRewritten."


def test_unknown_document_raises(session_factory):
    """Fetch or raise: shared by every endpoint."""
    engine, _, _ = build_engine(session_factory)
    with pytest.raises(EditedDocumentNotFoundError):
        engine.get(999)


# --- Dwight the pure reviser ---


def test_revise_returns_a_proposal_with_its_diff(session_factory, ryan):
    """One complete_validated call; nothing persisted; diff computed."""
    revised = "## Wins\n\nPrince Family Paper renewal signed. Q3 reporting is up to date."
    engine, llm, _ = build_engine(
        session_factory, [json.dumps({"content_md": revised})]
    )
    doc = engine.create(create_payload(ryan))
    segment_id = add_validated_segment(
        session_factory, ryan["entry_id"], EntityType.TEAM_MEMBER, ryan["member_id"],
        "Q3 reporting is up to date.", GENERATED_AT + timedelta(days=3),
    )
    revision = engine.revise(doc.id, "Add the reporting point.", [segment_id])
    assert revision.content_md == revised
    assert any(s.op == "insert" for s in revision.diff)
    # The proposal is NOT the document: saving is a separate gesture.
    assert engine.get(doc.id).content_md == create_payload(ryan).content_md
    # The context traveled: document and selected excerpt in the prompt.
    prompt = llm.complete_calls[0][1]["content"]
    assert "Prince Family Paper renewal signed" in prompt
    assert "Q3 reporting is up to date" in prompt


def test_revise_starts_from_the_canvas_override(session_factory, ryan):
    """C3: unsaved canvas edits travel to Dwight, not the stale save."""
    engine, llm, _ = build_engine(
        session_factory, [json.dumps({"content_md": "canvas text, shorter"})]
    )
    doc = engine.create(create_payload(ryan))
    revision = engine.revise(
        doc.id, "Shorten it.", [], content_md="Canvas text the manager just typed."
    )
    prompt = llm.complete_calls[0][1]["content"]
    assert "Canvas text the manager just typed." in prompt
    # The diff is against the canvas, not the saved state.
    rebuilt_before = "".join(s.text for s in revision.diff if s.op in ("equal", "delete"))
    assert rebuilt_before == "Canvas text the manager just typed."


def test_revise_draft_needs_no_document(session_factory):
    """C3: 'Edit' persists nothing - a draft is revised without an id."""
    engine, llm, _ = build_engine(
        session_factory, [json.dumps({"content_md": "Draft, revised."})]
    )
    revision = engine.revise_draft("Draft as generated.", "Make it punchy.")
    assert revision.document_id is None
    assert revision.content_md == "Draft, revised."
    assert any(s.op == "insert" for s in revision.diff)


# --- the corpus entry and the person exception ---


def test_client_document_enters_the_corpus(session_factory, ryan):
    """A client-targeted save files a scranton document, manager tag 1.0."""
    engine, _, store = build_engine(session_factory)
    doc = engine.create(
        create_payload(
            ryan,
            title="Client - Prince Family Paper",
            template_key="client_file",
            target_entity_type=EntityType.CLIENT,
            target_entity_id=ryan["client_id"],
        )
    )
    with session_factory() as session:
        row = session.query(Document).filter_by(origin_ref=f"scranton:{doc.id}").one()
        assert row.source == "scranton"
        assert row.tags[0].entity_type == EntityType.CLIENT
        assert row.tags[0].confidence == 1.0
        assert row.chunks
    assert store.upserted  # embedded into the documents collection


def test_person_document_never_enters_the_corpus(session_factory, ryan):
    """The person exception: 1:1 briefs stay out of Pam's memory."""
    engine, _, store = build_engine(session_factory)
    doc = engine.create(create_payload(ryan))
    with session_factory() as session:
        assert (
            session.query(Document)
            .filter_by(origin_ref=f"scranton:{doc.id}")
            .first()
            is None
        )
    assert store.upserted == []


def test_resave_reindexes_the_corpus_document(session_factory, ryan):
    """A content change re-chunks and re-embeds, same documents row."""
    engine, _, store = build_engine(session_factory)
    doc = engine.create(
        create_payload(
            ryan,
            title="Client - Prince Family Paper",
            template_key="client_file",
            target_entity_type=EntityType.CLIENT,
            target_entity_id=ryan["client_id"],
        )
    )
    first_upserts = len(store.upserted)
    engine.save(doc.id, EditedDocumentUpdate(content_md="## Wins\n\nNew content."))
    with session_factory() as session:
        rows = session.query(Document).filter_by(origin_ref=f"scranton:{doc.id}").all()
        assert len(rows) == 1
        assert rows[0].chunks[0].content.startswith("## Wins")
    assert len(store.upserted) > first_upserts


def test_drive_sync_never_touches_scranton_documents(session_factory, ryan):
    """An empty source sync must not soft-delete Scranton-born rows."""
    engine, _, _ = build_engine(session_factory)
    doc = engine.create(
        create_payload(
            ryan,
            title="Client - Prince Family Paper",
            template_key="client_file",
            target_entity_type=EntityType.CLIENT,
            target_entity_id=ryan["client_id"],
        )
    )
    report = engine.darryl.sync()
    assert report.removed == 0
    with session_factory() as session:
        row = session.query(Document).filter_by(origin_ref=f"scranton:{doc.id}").one()
        assert row.deleted_at is None
