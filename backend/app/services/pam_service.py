"""Ask Pam: question -> retrieve -> grounded answer with sources.

ONE Pam, TWO memories (owner arbitration, 2026-07-15): the human layer
(validated segments) and Darryl's documentary corpus live in separate
vector collections with different lifecycles, but a question queries
both and the answer weaves them, sources badged 'team memory' or
'document' with the clickable link back to the original.

The retrieval contract is inherited from M1's design decisions:
- Only VALIDATED segments live in the segments store, so nothing
  rejected or merely proposed can ever surface in an answer. On the
  corpus side the gate is the sharing gesture itself: everything in
  the collection is answerable by construction.
- Chroma returns ids and scores only; the text of truth is re-read from
  SQLite. If the two stores ever disagree, SQLite wins. The corpus
  lifecycle rules (deleted documents are gone, older versions silent
  unless every version is asked for) apply at that re-read, never in
  the index - which is why the vectors' metadata can stay static.

Noise control (owner QA, 2026-07-14: "de nombreuses sources non
pertinentes apparaissent"): two filters keep the sources honest.
- A similarity floor (min_score, env PAM_MIN_SCORE) drops far-fetched
  hits before they even reach the model.
- Only excerpts the answer actually cites [n] are returned as sources;
  an answer that cites nothing shows no sources at all (prompt rule 3:
  unrelated excerpts mean an honest empty, never a source list).

Deliberate M2 scope cut (documented in docs/ask_pam.md): no clarify
step. Ambiguous questions are handled by the grounded prompt's honesty
rule ("say when the memory does not contain the answer") instead of a
second LLM round-trip.
"""

import re

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from backend.app.adapters.llm.base import LLMProvider
from backend.app.adapters.vectorstore.base import Hit, VectorStore
from backend.app.domain.models import (
    Client,
    DataType,
    Document,
    DocumentChunk,
    EntityType,
    EntrySegment,
    Project,
    SegmentTag,
    TeamMember,
    ValidationStatus,
)
from backend.app.domain.schemas import PamAnswer, PamSource
from backend.app.services.darryl_service import normalize_text
from backend.app.services.prompts import build_pam_messages

# Deterministic and free: when retrieval finds nothing there is no point
# paying for a model call just to say "no memory". English on purpose:
# UI text is English (SCRANTON_CONTEXT section 8).
NO_MEMORY_ANSWER = "Pam has no validated memory matching this question yet."

# People are not Pam's department (owner, QA 2026-07-14): a broad
# question about one person gets a deterministic redirect, zero noise.
PEOPLE_REDIRECT_ANSWER = (
    "People are not my department: what the team shares and signals lives "
    "in Meet Toby, and the one-on-one briefs in Michael's Desk (manager "
    "view). I keep the operational memory - projects, clients, commitments."
)

# Broad-intent markers, French and English (the owner's two working
# languages - same closed-set philosophy as the language pin). A broad
# question about ONE known entity is served as a summary template.
BROAD_INTENT_MARKERS = (
    "infos sur", "info sur", "le point sur", "point sur", "statut",
    "tout sur", "tout savoir", "ou en est", "où en est", "où on en est",
    "la fiche", "brief", "résume", "resume-moi", "résumé de",
    "status", "everything on", "everything about", "catch me up",
    "full picture", "update on", "where do we stand", "sum up",
)

# Entity kind -> the template that IS the answer for a broad question.
# NO team_member here (owner, QA 2026-07-14): people information is
# Meet Toby's and Michael's Desk's job, manager-only. Pam never serves
# a person's picture.
TEMPLATE_BY_KIND = {
    "project": "project_file",
    "client": "client_file",
}

# Cap on the supporting excerpts of the deterministic two-member answer.
SHARED_WORK_SOURCE_CAP = 6

# Explicit all-versions intent (owner arbitration, 2026-07-15: latest
# by default, ALL versions when asked). Closed-set markers, French and
# English, like the broad-intent list above.
VERSION_INTENT_MARKERS = (
    "toutes les versions", "chaque version", "les versions",
    "all versions", "every version", "each version", "version history",
)


class PamService:
    """Orchestrates the retrieval pipeline. Pure logic: all I/O behind seams."""

    def __init__(
        self,
        llm: LLMProvider,
        session_factory: sessionmaker[Session],
        vector_store: VectorStore,
        summary_service=None,
        min_score: float = 0.6,
        doc_vector_store: VectorStore | None = None,
    ) -> None:
        """Wire the seams. summary_service powers the template answers
        (recadrage 2026-07-12); without it Pam is plain Q&A, which keeps
        older tests and callers valid. min_score is the retrieval floor
        (settings.pam_min_score): hits below it are noise, not memory.
        doc_vector_store is the second memory (Darryl's corpus); None
        keeps Pam single-memory, same backward-compatibility idea."""
        self.llm = llm
        self.session_factory = session_factory
        self.vector_store = vector_store
        self.summary_service = summary_service
        self.min_score = min_score
        self.doc_vector_store = doc_vector_store

    def query(self, question: str, *, filters: dict | None = None, k: int = 8) -> PamAnswer:
        """Answer a plain-language question over the validated memory.

        filters is not exposed through the API yet (M2 keeps the surface
        minimal) but the seam accepts it so entity- or view-scoped
        queries plug in without a signature change.
        """
        served = self._serve_routed(question)
        if served is not None:
            return served
        versions = self._serve_versions(question)
        if versions is not None:
            return versions

        embedding = self.llm.embed([question])[0]
        # Pam answers from the COLD layer only (owner, QA 2026-07-14):
        # warm observations about people belong to Meet Toby and to the
        # Desk briefs, manager-only. With roles in the UI, a member
        # asking Pam must never surface a colleague's confidences.
        cold_filters = {"data_type": "cold", **(filters or {})}
        segment_hits = self._floored(
            self.vector_store.query(embedding, filters=cold_filters, k=k)
        )
        # The second memory: the corpus is cold by construction, so no
        # filter is needed - lifecycle rules apply at the SQLite re-read.
        document_hits = (
            self._floored(self.doc_vector_store.query(embedding, k=k))
            if self.doc_vector_store is not None
            else []
        )
        if not segment_hits and not document_hits:
            return PamAnswer(answer=NO_MEMORY_ANSWER, sources=[])

        with self.session_factory() as session:
            sources = self._load_sources(session, segment_hits)
            sources += self._load_document_sources(session, document_hits)

        if not sources:
            # Hits pointed at rows SQLite no longer has (or at silenced
            # versions): treat as empty rather than answering from ghosts.
            return PamAnswer(answer=NO_MEMORY_ANSWER, sources=[])

        # One weave: best excerpts first whatever their memory, capped at
        # k, then numbered - the refs the citations will use.
        sources.sort(key=lambda source: -(source.score or 0.0))
        sources = sources[:k]
        for ref, source in enumerate(sources, start=1):
            source.ref = ref

        context_block = "\n".join(self._context_line(source) for source in sources)
        answer = self.llm.complete(build_pam_messages(question, context_block))
        return PamAnswer(answer=answer, sources=self._cited_only(answer, sources))

    def _floored(self, hits: list[Hit]) -> list[Hit]:
        """Apply the retrieval floor: below min_score is noise, not memory."""
        return [hit for hit in hits if hit.score is None or hit.score >= self.min_score]

    @staticmethod
    def _context_line(source: PamSource) -> str:
        """One prompt line, labeled with the memory the excerpt came from."""
        label = (
            f"document: {source.title}" if source.kind == "document" else "team memory"
        )
        return f"[{source.ref}] ({source.created_at:%Y-%m-%d}) [{label}] {source.content}"

    @staticmethod
    def _cited_only(answer: str, sources: list[PamSource]) -> list[PamSource]:
        """Keep only the excerpts the answer actually cites.

        The excerpt number (ref) survives the filter so the displayed
        [n] still matches the citations in the text. No citation at all
        means the model found the excerpts unrelated (prompt rule 3):
        showing them anyway is exactly the noise the QA flagged.
        """
        cited = {int(number) for number in re.findall(r"\[(\d+)\]", answer)}
        return [source for source in sources if source.ref in cited]

    @staticmethod
    def _load_document_sources(session: Session, hits: list[Hit]) -> list[PamSource]:
        """Re-read hit chunks from SQLite, applying the corpus lifecycle.

        This re-read is where the rules live (the index metadata stays
        static): a chunk whose document is gone answers nothing, and an
        older version stays silent - the latest of the family is the
        one that speaks by default (owner arbitration, 2026-07-15).
        """
        chunks = session.scalars(
            select(DocumentChunk).where(
                DocumentChunk.id.in_([hit.segment_id for hit in hits])
            )
        ).all()
        by_id = {chunk.id: chunk for chunk in chunks}
        sources = []
        for hit in hits:
            chunk = by_id.get(hit.segment_id)
            if chunk is None:
                continue
            document = chunk.document
            if document is None or document.deleted_at is not None:
                continue
            if not document.is_latest:
                continue
            sources.append(
                PamSource(
                    kind="document",
                    document_id=document.id,
                    title=document.title,
                    link=document.web_view_link,
                    content=chunk.content,
                    # Cold by construction; 1 is the objective floor.
                    data_type=DataType.COLD,
                    sensitivity_level=1,
                    score=hit.score,
                    created_at=document.modified_at or document.ingested_at,
                )
            )
        return sources

    # --- deterministic routes (templates, people, versions), no LLM ---

    def _serve_versions(self, question: str) -> PamAnswer | None:
        """List every version of a document family, on explicit demand.

        Deterministic SQL, no LLM (owner arbitration, 2026-07-15: the
        latest answers by default, but 'toutes les versions' means all
        of them). The family is matched by its normalized key appearing
        in the question; no match falls through to grounded RAG.
        """
        lowered = question.lower()
        if not any(marker in lowered for marker in VERSION_INTENT_MARKERS):
            return None
        normalized_question = normalize_text(question)
        with self.session_factory() as session:
            documents = session.scalars(
                select(Document).where(Document.deleted_at.is_(None))
            ).all()
        families: dict[str, list[Document]] = {}
        for document in documents:
            if document.family_key and document.family_key in normalized_question:
                families.setdefault(document.family_key, []).append(document)
        if not families:
            return None

        sources: list[PamSource] = []
        parts: list[str] = []
        for family_key, members in sorted(families.items()):
            members.sort(
                key=lambda doc: (doc.modified_at or doc.ingested_at), reverse=True
            )
            parts.append(
                f"The archive holds {len(members)} version(s) of '{family_key}', "
                "newest first - the latest is the one that answers by default."
            )
            for document in members:
                sources.append(
                    PamSource(
                        ref=len(sources) + 1,
                        kind="document",
                        document_id=document.id,
                        title=document.title,
                        link=document.web_view_link,
                        content=(
                            f"{document.title} - folder: "
                            f"{document.folder_path or 'shared root'}"
                            + (" - current version" if document.is_latest else "")
                        ),
                        data_type=DataType.COLD,
                        sensitivity_level=1,
                        score=None,
                        created_at=document.modified_at or document.ingested_at,
                    )
                )
        return PamAnswer(answer=" ".join(parts), sources=sources)

    def _serve_routed(self, question: str) -> PamAnswer | None:
        """Route a broad question about known entities, closed-world.

        Summaries are Pam RESPONSE TEMPLATES (recadrage 2026-07-12): a
        broad question naming exactly ONE project or client is served as
        the matching living template. People stay out of Pam's answers
        (owner, QA 2026-07-14): one member named gets a redirect to Meet
        Toby / the Desk; two members named get the deterministic list of
        the projects and clients they share. Anything else (precise
        question, unknown or mixed names) falls through to grounded RAG.
        The clarify-before-answering Pam of slide 05 is the V2 upgrade.
        """
        lowered = question.lower()
        if not any(marker in lowered for marker in BROAD_INTENT_MARKERS):
            return None

        entity_matches: list[tuple[str, int, str]] = []
        member_matches: list[tuple[int, str]] = []
        with self.session_factory() as session:
            for kind, model in (("project", Project), ("client", Client)):
                for row in session.scalars(select(model)):
                    if row.name and row.name.lower() in lowered:
                        entity_matches.append((kind, row.id, row.name))
            for member in session.scalars(
                select(TeamMember).where(TeamMember.is_active.is_(True))
            ):
                if member.full_name and member.full_name.lower() in lowered:
                    member_matches.append((member.id, member.full_name))

        if member_matches and entity_matches:
            return None  # mixed picture: let grounded RAG sort it out
        if len(member_matches) == 1:
            return PamAnswer(answer=PEOPLE_REDIRECT_ANSWER, sources=[])
        if len(member_matches) == 2:
            return self._shared_work(member_matches)
        if len(entity_matches) == 1 and self.summary_service is not None:
            return self._serve_template(entity_matches[0])
        return None

    def _serve_template(self, match: tuple[str, int, str]) -> PamAnswer | None:
        """Serve the living template of one project or client."""
        kind, target_id, name = match
        try:
            summary = self.summary_service.generate(
                TEMPLATE_BY_KIND[kind], target_id, cold_only=True
            )
        except Exception:
            # A template hiccup must never block an answer: the grounded
            # Q&A path is always there as the fallback.
            return None
        return PamAnswer(
            answer=(
                f"Here is the full picture on {name} - "
                "assembled from everything validated."
            ),
            sources=summary.sources,
            summary=summary,
        )

    def _shared_work(self, members: list[tuple[int, str]]) -> PamAnswer:
        """What two members share: their common projects and clients.

        Deterministic SQL over validated tags, no LLM (owner, QA
        2026-07-14: a broad question on two people should say what they
        work on together). A link is a validated segment tagged with the
        member AND the project/client; only COLD segments are shown as
        sources - the warm layer never flows through Pam.
        """
        (id_a, name_a), (id_b, name_b) = members
        with self.session_factory() as session:
            links_a = self._work_links(session, id_a)
            links_b = self._work_links(session, id_b)
            shared = sorted(set(links_a) & set(links_b))
            if not shared:
                return PamAnswer(
                    answer=(
                        f"The validated memory shows no shared project or "
                        f"client for {name_a} and {name_b}. For who they "
                        "are beyond the work, Meet Toby is the place."
                    ),
                    sources=[],
                )
            labels = [self._entity_label(session, kind, entity_id) for kind, entity_id in shared]
            sources = self._shared_sources(session, (id_a, id_b), shared)
        listed = "; ".join(labels)
        return PamAnswer(
            answer=(
                f"{name_a} and {name_b} appear together on: {listed}. "
                "That is the operational overlap the validated memory holds."
            ),
            sources=sources,
        )

    @staticmethod
    def _work_links(session: Session, member_id: int) -> set[tuple[str, int]]:
        """The (kind, id) projects and clients a member is tagged with.

        A link means: one VALIDATED segment carries both the member tag
        and the project/client tag - the segment is the evidence.
        """
        member_segments = (
            select(SegmentTag.segment_id)
            .join(EntrySegment, EntrySegment.id == SegmentTag.segment_id)
            .where(
                SegmentTag.entity_type == EntityType.TEAM_MEMBER,
                SegmentTag.entity_id == member_id,
                EntrySegment.validation_status == ValidationStatus.VALIDATED,
            )
        )
        rows = session.execute(
            select(SegmentTag.entity_type, SegmentTag.entity_id)
            .where(
                SegmentTag.segment_id.in_(member_segments),
                SegmentTag.entity_type.in_([EntityType.PROJECT, EntityType.CLIENT]),
                SegmentTag.entity_id.is_not(None),
            )
            .distinct()
        )
        return {(entity_type.value, entity_id) for entity_type, entity_id in rows}

    @staticmethod
    def _entity_label(session: Session, kind: str, entity_id: int) -> str:
        """Human label of one shared entity: 'Name (project|client)'."""
        model = Project if kind == "project" else Client
        row = session.get(model, entity_id)
        name = row.name if row else f"{kind} #{entity_id}"
        return f"{name} ({kind})"

    def _shared_sources(
        self,
        session: Session,
        member_ids: tuple[int, int],
        shared: list[tuple[str, int]],
    ) -> list[PamSource]:
        """The cold validated segments linking either member to the
        shared entities - the receipts behind the deterministic answer."""
        member_segments = (
            select(SegmentTag.segment_id)
            .where(
                SegmentTag.entity_type == EntityType.TEAM_MEMBER,
                SegmentTag.entity_id.in_(member_ids),
            )
        )
        entity_clauses = [
            (SegmentTag.entity_type == EntityType(kind)) & (SegmentTag.entity_id == entity_id)
            for kind, entity_id in shared
        ]
        entity_filter = entity_clauses[0]
        for clause in entity_clauses[1:]:
            entity_filter = entity_filter | clause
        segment_ids = session.scalars(
            select(SegmentTag.segment_id)
            .where(SegmentTag.segment_id.in_(member_segments), entity_filter)
            .distinct()
        ).all()
        segments = session.scalars(
            select(EntrySegment)
            .where(
                EntrySegment.id.in_(segment_ids),
                EntrySegment.validation_status == ValidationStatus.VALIDATED,
                EntrySegment.data_type == DataType.COLD,
            )
            .order_by(EntrySegment.created_at.desc())
            .limit(SHARED_WORK_SOURCE_CAP)
        ).all()
        return [
            PamSource(
                ref=index,
                segment_id=segment.id,
                entry_id=segment.entry_id,
                content=segment.content,
                data_type=segment.data_type,
                sensitivity_level=segment.sensitivity_level,
                score=None,
                created_at=segment.created_at,
            )
            for index, segment in enumerate(segments, start=1)
        ]

    @staticmethod
    def _load_sources(session: Session, hits: list[Hit]) -> list[PamSource]:
        """Re-read hit segments from SQLite, preserving relevance order.

        A hit whose id is missing from SQLite is silently skipped: the
        relational store is the source of truth, not the index. ref is
        the excerpt number the prompt and the citations share.
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
                    ref=len(sources) + 1,
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
