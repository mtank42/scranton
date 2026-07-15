"""Darryl pipeline: sync, routing, the bin, versions, lifecycle.

Same testing philosophy as Dwight: the source and the model are
scripted, the pipeline around the seams is what gets asserted. A
ScriptedLLMProvider with NO queued completions doubles as a proof that
deterministic routing never wakes the model.
"""

from datetime import datetime, timezone

import pytest

from backend.app.adapters.documents.base import DocumentSource, SourceDocument
from backend.app.domain.models import (
    Client,
    Document,
    DocumentChunk,
    DocumentProposedBy,
    DocumentStatus,
    EntityType,
    Project,
)
from backend.app.services.darryl_service import (
    DarrylService,
    UnknownEntityError,
    chunk_text,
    family_key_of,
)
from tests.conftest import FakeVectorStore, ScriptedLLMProvider


class FakeDocumentSource(DocumentSource):
    """Yields a mutable list of SourceDocuments: the scripted corpus."""

    def __init__(self, documents: list[SourceDocument] | None = None) -> None:
        self.documents = documents or []

    def fetch(self):
        yield from self.documents


def source_doc(**overrides) -> SourceDocument:
    """One SourceDocument with sensible defaults, overridable per test."""
    values = dict(
        origin_ref="gdrive:file-1",
        title="Rapport_SEO_mars.pdf",
        mime_type="application/pdf",
        folder_path="Clients/Techni-Pneus/2026",
        modified_at=datetime(2026, 3, 10, tzinfo=timezone.utc),
        web_view_link="https://drive.example/file-1",
        content_sha256="sha-1",
        text="SEO audit for March.\nOrganic traffic grew 12 percent.",
    )
    values.update(overrides)
    return SourceDocument(**values)


@pytest.fixture
def roster(session_factory):
    """A client and a project for routing to recognize."""
    with session_factory() as session:
        client = Client(name="Techni-Pneus")
        project = Project(name="Site redesign")
        session.add_all([client, project])
        session.commit()
        return {"client_id": client.id, "project_id": project.id}


def build_service(session_factory, source, completions=None, min_confidence=0.75):
    """Wire a DarrylService on scripted seams."""
    llm = ScriptedLLMProvider(completions or [])
    store = FakeVectorStore()
    service = DarrylService(
        source=source,
        llm=llm,
        session_factory=session_factory,
        vector_store=store,
        min_confidence=min_confidence,
    )
    return service, llm, store


# --- family key heuristic ---


def test_family_key_strips_version_markers():
    """The Fabrice case: six versions of one report are one family."""
    assert family_key_of("Rapport_SEO_final_V3_DEF(1).pdf") == "rapport seo"
    assert family_key_of("Rapport SEO.pdf") == "rapport seo"
    assert family_key_of("rapport-seo-draft.docx") == "rapport seo"


def test_family_key_keeps_years_apart():
    """'Bilan 2025' and 'Bilan 2026' are different documents, not versions."""
    assert family_key_of("Bilan 2025.pdf") != family_key_of("Bilan 2026.pdf")


def test_chunk_text_packs_paragraphs():
    """Paragraphs are packed whole, split only across the size target."""
    text = "\n".join(f"Paragraph number {i} with some content." for i in range(80))
    chunks = chunk_text(text)
    assert len(chunks) > 1
    assert all(len(chunk) <= 1300 for chunk in chunks)
    # Nothing lost: every paragraph survives in some chunk.
    assert sum(chunk.count("Paragraph number") for chunk in chunks) == 80


# --- routing ---


def test_deterministic_routing_from_folder_path(session_factory, roster):
    """A client named in the path routes silently - and never wakes the LLM."""
    source = FakeDocumentSource([source_doc()])
    service, llm, store = build_service(session_factory, source)

    report = service.sync()

    assert report.added == 1 and report.unclassified == 0
    assert llm.complete_calls == []  # deterministic means deterministic
    with session_factory() as session:
        document = session.query(Document).one()
        assert document.status == DocumentStatus.INDEXED
        assert [(t.entity_type, t.entity_id, t.confidence) for t in document.tags] == [
            (EntityType.CLIENT, roster["client_id"], 1.0)
        ]
        assert document.tags[0].proposed_by == DocumentProposedBy.DARRYL
        assert len(document.chunks) >= 1
    # One vector per chunk, scalar metadata only, cold by construction.
    assert store.upserted and all(
        vector.metadata["data_type"] == "cold" and "document_id" in vector.metadata
        for vector in store.upserted
    )


def test_llm_fallback_routes_above_the_floor(session_factory, roster):
    """No deterministic signal: the model's confident opinion routes."""
    source = FakeDocumentSource(
        [source_doc(folder_path="Archives/2026", title="notes_reunion.pdf")]
    )
    answer = (
        '{"tags": [{"entity_type": "client", '
        f'"entity_id": {roster["client_id"]}, "confidence": 0.9}}]}}'
    )
    service, llm, store = build_service(session_factory, source, completions=[answer])

    report = service.sync()

    assert report.unclassified == 0
    with session_factory() as session:
        document = session.query(Document).one()
        assert document.status == DocumentStatus.INDEXED
        assert document.tags[0].confidence == 0.9


def test_hesitant_or_unknown_llm_answers_mean_the_bin(session_factory, roster):
    """Below the floor or outside the roster: unclassified, never a bet."""
    hesitant = '{"tags": [{"entity_type": "client", "entity_id": %d, "confidence": 0.5}]}' % (
        roster["client_id"]
    )
    unknown = '{"tags": [{"entity_type": "project", "entity_id": 999, "confidence": 0.95}]}'
    source = FakeDocumentSource(
        [
            source_doc(origin_ref="gdrive:a", title="doc_a.pdf", folder_path="Misc"),
            source_doc(origin_ref="gdrive:b", title="doc_b.pdf", folder_path="Misc"),
        ]
    )
    service, llm, store = build_service(
        session_factory, source, completions=[hesitant, unknown]
    )

    report = service.sync()

    assert report.added == 2 and report.unclassified == 2
    with session_factory() as session:
        documents = session.query(Document).all()
        assert all(d.status == DocumentStatus.UNCLASSIFIED for d in documents)
        assert all(d.tags == [] for d in documents)
        # The bin stays queryable: chunks exist and were embedded.
        assert session.query(DocumentChunk).count() == 2
    assert len(store.upserted) == 2


def test_spreadsheets_are_cataloged_not_extracted(session_factory, roster):
    """xlsx: name, date, folder and link enter the corpus - never content."""
    source = FakeDocumentSource(
        [
            source_doc(
                title="Suivi_Techni-Pneus.xlsx",
                mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                folder_path="Clients",
                text=None,
            )
        ]
    )
    service, llm, store = build_service(session_factory, source)

    service.sync()

    with session_factory() as session:
        document = session.query(Document).one()
        assert document.status == DocumentStatus.CATALOGED
        # One catalog chunk carrying identity, so meaning-search finds it.
        assert len(document.chunks) == 1
        assert "Suivi_Techni-Pneus.xlsx" in document.chunks[0].content


# --- versions ---


def test_latest_version_wins_inside_a_family(session_factory, roster):
    """Two versions, one family: only the most recent answers by default."""
    source = FakeDocumentSource(
        [
            source_doc(
                origin_ref="gdrive:v1",
                title="Rapport_SEO_V1.pdf",
                modified_at=datetime(2026, 1, 5, tzinfo=timezone.utc),
                content_sha256="sha-v1",
            ),
            source_doc(
                origin_ref="gdrive:v2",
                title="Rapport_SEO_final_V3_DEF(1).pdf",
                modified_at=datetime(2026, 3, 20, tzinfo=timezone.utc),
                content_sha256="sha-v2",
            ),
        ]
    )
    service, llm, store = build_service(session_factory, source)

    service.sync()

    with session_factory() as session:
        by_ref = {d.origin_ref: d for d in session.query(Document).all()}
        assert by_ref["gdrive:v1"].family_key == by_ref["gdrive:v2"].family_key
        assert not by_ref["gdrive:v1"].is_latest
        assert by_ref["gdrive:v2"].is_latest


# --- lifecycle: resync ---


def test_changed_content_reindexes_and_keeps_routing(session_factory, roster):
    """A new sha replaces the chunks and vectors; the filing survives."""
    document = source_doc()
    source = FakeDocumentSource([document])
    service, llm, store = build_service(session_factory, source)
    service.sync()
    with session_factory() as session:
        old_chunk_ids = [c.id for c in session.query(DocumentChunk).all()]

    source.documents = [
        source_doc(content_sha256="sha-2", text="Entirely rewritten SEO audit.")
    ]
    report = service.sync()

    assert report.updated == 1 and report.added == 0
    assert store.deleted == old_chunk_ids
    with session_factory() as session:
        refreshed = session.query(Document).one()
        assert refreshed.content_sha256 == "sha-2"
        assert refreshed.tags != []  # routing kept
        contents = [c.content for c in refreshed.chunks]
        assert contents == ["Entirely rewritten SEO audit."]


def test_removed_document_is_soft_deleted_and_unindexed(session_factory, roster):
    """Gone from the folder: consent withdrawn - row stays, vectors leave."""
    source = FakeDocumentSource([source_doc()])
    service, llm, store = build_service(session_factory, source)
    service.sync()

    source.documents = []
    report = service.sync()

    assert report.removed == 1
    with session_factory() as session:
        document = session.query(Document).one()
        assert document.deleted_at is not None
    assert store.deleted != []


def test_unchanged_document_is_left_alone(session_factory, roster):
    """Same sha twice: no re-embedding, no duplicate chunks."""
    source = FakeDocumentSource([source_doc()])
    service, llm, store = build_service(session_factory, source)
    service.sync()
    embeds_after_first = len(llm.embed_calls)

    report = service.sync()

    assert report.added == 0 and report.updated == 0
    assert len(llm.embed_calls) == embeds_after_first
    with session_factory() as session:
        assert session.query(Document).count() == 1


# --- the manager's corrections ---


def test_classify_files_a_binned_document(session_factory, roster):
    """One click out of the bin: manager tag, status recomputed."""
    source = FakeDocumentSource(
        [source_doc(folder_path="Misc", title="mystery.pdf")]
    )
    service, llm, store = build_service(
        session_factory, source, completions=['{"tags": []}']
    )
    service.sync()
    with session_factory() as session:
        document_id = session.query(Document).one().id

    result = service.classify(document_id, EntityType.PROJECT, roster["project_id"])

    assert result.status == DocumentStatus.INDEXED
    assert [(t.entity_type, t.entity_id) for t in result.tags] == [
        (EntityType.PROJECT, roster["project_id"])
    ]
    assert result.tags[0].proposed_by == DocumentProposedBy.MANAGER


def test_classify_rejects_unknown_entities(session_factory, roster):
    """Closed world applies to the manager too."""
    source = FakeDocumentSource([source_doc()])
    service, llm, store = build_service(session_factory, source)
    service.sync()
    with session_factory() as session:
        document_id = session.query(Document).one().id

    with pytest.raises(UnknownEntityError):
        service.classify(document_id, EntityType.CLIENT, 999)


def test_recent_and_unclassified_surfaces(session_factory, roster):
    """The Pam overlay strip: newest first, the bin filtered."""
    source = FakeDocumentSource(
        [
            source_doc(),
            source_doc(origin_ref="gdrive:x", title="mystery.pdf", folder_path="Misc"),
        ]
    )
    service, llm, store = build_service(
        session_factory, source, completions=['{"tags": []}']
    )
    service.sync()

    recent = service.recent(limit=5)
    binned = service.unclassified()

    assert len(recent) == 2
    assert [d.title for d in binned] == ["mystery.pdf"]
