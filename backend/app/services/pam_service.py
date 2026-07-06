"""Ask Pam: question -> retrieve -> grounded answer with sources.

The retrieval contract is inherited from M1's design decisions:
- Only VALIDATED segments live in the vector store, so nothing rejected
  or merely proposed can ever surface in an answer. No status filter
  needed here: validation already was the gate.
- Chroma returns ids and scores only; the text of truth is re-read from
  SQLite. If the two stores ever disagree, SQLite wins.

Deliberate M2 scope cut (documented in docs/ask_pam.md): no clarify
step. Ambiguous questions are handled by the grounded prompt's honesty
rule ("say when the memory does not contain the answer") instead of a
second LLM round-trip.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from backend.app.adapters.llm.base import LLMProvider
from backend.app.adapters.vectorstore.base import Hit, VectorStore
from backend.app.domain.models import EntrySegment
from backend.app.domain.schemas import PamAnswer, PamSource
from backend.app.services.prompts import build_pam_messages

# Deterministic and free: when retrieval finds nothing there is no point
# paying for a model call just to say "no memory". English on purpose:
# UI text is English (SCRANTON_CONTEXT section 8).
NO_MEMORY_ANSWER = "Pam has no validated memory matching this question yet."


class PamService:
    """Orchestrates the retrieval pipeline. Pure logic: all I/O behind seams."""

    def __init__(
        self,
        llm: LLMProvider,
        session_factory: sessionmaker[Session],
        vector_store: VectorStore,
    ) -> None:
        """Wire the three seams the pipeline needs."""
        self.llm = llm
        self.session_factory = session_factory
        self.vector_store = vector_store

    def query(self, question: str, *, filters: dict | None = None, k: int = 8) -> PamAnswer:
        """Answer a plain-language question over the validated memory.

        filters is not exposed through the API yet (M2 keeps the surface
        minimal) but the seam accepts it so entity- or view-scoped
        queries plug in without a signature change.
        """
        embedding = self.llm.embed([question])[0]
        hits = self.vector_store.query(embedding, filters=filters, k=k)
        if not hits:
            return PamAnswer(answer=NO_MEMORY_ANSWER, sources=[])

        with self.session_factory() as session:
            sources = self._load_sources(session, hits)

        if not sources:
            # Hits pointed at segments SQLite no longer has: treat as empty
            # rather than answering from ghost content.
            return PamAnswer(answer=NO_MEMORY_ANSWER, sources=[])

        context_block = "\n".join(
            f"[{i}] ({source.created_at:%Y-%m-%d}) {source.content}"
            for i, source in enumerate(sources, start=1)
        )
        answer = self.llm.complete(build_pam_messages(question, context_block))
        return PamAnswer(answer=answer, sources=sources)

    @staticmethod
    def _load_sources(session: Session, hits: list[Hit]) -> list[PamSource]:
        """Re-read hit segments from SQLite, preserving relevance order.

        A hit whose id is missing from SQLite is silently skipped: the
        relational store is the source of truth, not the index.
        """
        segments = session.scalars(
            select(EntrySegment).where(
                EntrySegment.id.in_([hit.segment_id for hit in hits])
            )
        ).all()
        by_id = {segment.id: segment for segment in segments}
        sources = []
        for hit in hits:
            segment = by_id.get(hit.segment_id)
            if segment is None:
                continue
            sources.append(
                PamSource(
                    segment_id=segment.id,
                    entry_id=segment.entry_id,
                    content=segment.content,
                    data_type=segment.data_type,
                    sensitivity_level=segment.sensitivity_level,
                    score=hit.score,
                    created_at=segment.created_at,
                )
            )
        return sources
