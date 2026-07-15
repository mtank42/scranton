"""Pam's second memory: weaving documents into answers.

Scripted seams as everywhere: two FakeVectorStores (segments and
documents), a scripted model, real SQLite rows - the weave, the badges,
the links and the lifecycle rules are what gets asserted.
"""

from datetime import datetime

from backend.app.adapters.vectorstore.base import Hit
from backend.app.domain.models import (
    DataType,
    Document,
    DocumentChunk,
    DocumentStatus,
    Entry,
    EntrySegment,
    ProcessingStatus,
    SourceType,
    ValidationStatus,
)
from backend.app.services.pam_service import NO_MEMORY_ANSWER, PamService
from tests.conftest import FakeVectorStore, ScriptedLLMProvider


def add_segment(session_factory, content: str) -> int:
    """One validated cold segment, returning its id."""
    with session_factory() as session:
        entry = Entry(
            raw_content=content,
            source_type=SourceType.NOTE,
            processing_status=ProcessingStatus.COMPLETE,
        )
        session.add(entry)
        session.flush()
        segment = EntrySegment(
            entry_id=entry.id,
            content=content,
            segment_order=0,
            data_type=DataType.COLD,
            sensitivity_level=1,
            validation_status=ValidationStatus.VALIDATED,
        )
        session.add(segment)
        session.commit()
        return segment.id


def add_document(
    session_factory,
    title: str = "Rapport_SEO_mars.pdf",
    chunk_content: str = "SEO report for March: organic traffic grew.",
    is_latest: bool = True,
    deleted: bool = False,
    family_key: str = "rapport seo",
    modified_at: datetime | None = datetime(2026, 3, 10),
    link: str | None = "https://drive.example/doc",
) -> int:
    """One corpus document with a single chunk, returning the CHUNK id."""
    with session_factory() as session:
        document = Document(
            title=title,
            mime_type="application/pdf",
            source="gdrive",
            origin_ref=f"gdrive:{title}",
            web_view_link=link,
            folder_path="Clients/Techni-Pneus",
            modified_at=modified_at,
            content_sha256=f"sha-{title}",
            status=DocumentStatus.INDEXED,
            family_key=family_key,
            is_latest=is_latest,
            deleted_at=datetime(2026, 7, 1) if deleted else None,
        )
        session.add(document)
        session.flush()
        chunk = DocumentChunk(document_id=document.id, chunk_order=0, content=chunk_content)
        session.add(chunk)
        session.commit()
        return chunk.id


def build_pam(session_factory, completions, segment_hits=None, document_hits=None):
    """Pam wired on the two scripted memories."""
    llm = ScriptedLLMProvider(completions)
    service = PamService(
        llm=llm,
        session_factory=session_factory,
        vector_store=FakeVectorStore(segment_hits or []),
        doc_vector_store=FakeVectorStore(document_hits or []),
        min_score=0.6,
    )
    return service, llm


def test_answer_weaves_both_memories(session_factory):
    """One question, two memories: badged sources, refs shared with [n]."""
    segment_id = add_segment(session_factory, "Promised the SEO report by March 15.")
    chunk_id = add_document(session_factory)
    service, llm = build_pam(
        session_factory,
        completions=["Promised on the 15th [1], delivered in the March report [2]."],
        segment_hits=[Hit(segment_id=segment_id, score=0.9, metadata={})],
        document_hits=[Hit(segment_id=chunk_id, score=0.8, metadata={})],
    )

    answer = service.query("What did we deliver to Techni-Pneus?")

    kinds = [source.kind for source in answer.sources]
    assert kinds == ["memory", "document"]  # best score first, then numbered
    assert [source.ref for source in answer.sources] == [1, 2]
    document_source = answer.sources[1]
    assert document_source.title == "Rapport_SEO_mars.pdf"
    assert document_source.link == "https://drive.example/doc"
    # The prompt labeled each excerpt with its memory.
    context = llm.complete_calls[0][-1]["content"]
    assert "[team memory]" in context and "[document: Rapport_SEO_mars.pdf]" in context


def test_document_only_answers_work(session_factory):
    """The corpus alone can ground an answer (the Fabrice day-30 case)."""
    chunk_id = add_document(session_factory)
    service, llm = build_pam(
        session_factory,
        completions=["The March SEO report covers it [1]."],
        document_hits=[Hit(segment_id=chunk_id, score=0.85, metadata={})],
    )

    answer = service.query("Where is the SEO audit?")

    assert answer.sources[0].kind == "document"


def test_older_versions_and_deleted_documents_stay_silent(session_factory):
    """Lifecycle at the re-read: non-latest and deleted chunks answer nothing."""
    old_chunk = add_document(
        session_factory, title="Rapport_SEO_V1.pdf", is_latest=False
    )
    gone_chunk = add_document(
        session_factory, title="Removed.pdf", family_key="removed", deleted=True
    )
    service, llm = build_pam(
        session_factory,
        completions=[],
        document_hits=[
            Hit(segment_id=old_chunk, score=0.9, metadata={}),
            Hit(segment_id=gone_chunk, score=0.9, metadata={}),
        ],
    )

    answer = service.query("Where is the SEO audit?")

    assert answer.answer == NO_MEMORY_ANSWER and answer.sources == []
    assert llm.complete_calls == []  # nothing to ground means no model call


def test_retrieval_floor_applies_to_documents_too(session_factory):
    """A far-fetched corpus hit is noise, exactly like a segment one."""
    chunk_id = add_document(session_factory)
    service, llm = build_pam(
        session_factory,
        completions=[],
        document_hits=[Hit(segment_id=chunk_id, score=0.3, metadata={})],
    )

    answer = service.query("Anything about llamas?")

    assert answer.answer == NO_MEMORY_ANSWER


def test_all_versions_on_explicit_demand(session_factory):
    """'Toutes les versions' lists the family, deterministic, no LLM."""
    add_document(
        session_factory,
        title="Rapport_SEO_V1.pdf",
        is_latest=False,
        modified_at=datetime(2026, 1, 5),
    )
    add_document(
        session_factory,
        title="Rapport_SEO_final_V3_DEF(1).pdf",
        modified_at=datetime(2026, 3, 20),
    )
    service, llm = build_pam(session_factory, completions=[])

    answer = service.query("Montre-moi toutes les versions du rapport SEO")

    assert llm.complete_calls == [] and llm.embed_calls == []
    assert "2 version(s)" in answer.answer
    # Newest first, the current one flagged, links carried.
    assert [source.title for source in answer.sources] == [
        "Rapport_SEO_final_V3_DEF(1).pdf",
        "Rapport_SEO_V1.pdf",
    ]
    assert "current version" in answer.sources[0].content
    assert all(source.link for source in answer.sources)


def test_version_intent_without_a_known_family_falls_through(session_factory):
    """No matching family: grounded RAG handles it (here: empty memory)."""
    add_document(session_factory)
    service, llm = build_pam(session_factory, completions=[])

    answer = service.query("toutes les versions du contrat cadre")

    assert answer.answer == NO_MEMORY_ANSWER  # RAG path, which found nothing
    assert llm.embed_calls != []  # proof it fell through to retrieval
