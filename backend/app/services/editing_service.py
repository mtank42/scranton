"""The document-editing engine: save -> delta -> revise -> save again.

Surface-independent by design (owner, 2026-07-15): Michael's Desk and
the Pam cards call it today, Oscar's entity files will call it
tomorrow. A document goes in, an instruction goes in, a document comes
out - the engine never knows which screen asked.

Design decisions (owner arbitrations, 2026-07-16 - docs/document_editing.md):
- Templates stay LIVING; the first edit persists a snapshot that never
  changes on its own. The gap with the moving memory is PRESENTED as
  proposals (the delta) and only a manager gesture weaves them in.
- Dwight is a PURE REVISER ('option B is Dwight playing Pam'): one
  complete_validated call over document + instruction + selected
  excerpts, zero memory access of his own.
- The review diff is COMPUTED (difflib), never self-reported by the
  model: the highlighting is guaranteed by the calculation.
- Client/project documents feed Darryl's corpus at each save (the save
  gesture IS the filing); person-targeted documents NEVER do - people
  never flow through Pam.
"""

from difflib import SequenceMatcher
import re

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from backend.app.adapters.llm.base import LLMProvider
from backend.app.domain.models import (
    EditedDocument,
    EntityType,
    EntrySegment,
    SegmentTag,
    ValidationStatus,
    utcnow,
)
from backend.app.domain.schemas import (
    DiffSpan,
    DocumentDelta,
    DocumentRevision,
    DwightRevision,
    EditedDocumentCreate,
    EditedDocumentOut,
    EditedDocumentUpdate,
    PamSource,
)
from backend.app.services.darryl_service import DarrylService, naive_utc
from backend.app.services.llm_json import LLMContractError, complete_validated
from backend.app.services.prompts import build_revision_messages


class EditedDocumentNotFoundError(Exception):
    """The requested edited document id does not exist."""


class RevisionProcessingError(Exception):
    """The model could not produce a valid revision (after one retry)."""


# Only these targets feed the corpus: a 1:1 brief or annual-review
# material is a PERSON document and Pam never serves people (owner
# arbitrations, 2026-07-14 and 2026-07-16).
CORPUS_TARGETS = {EntityType.CLIENT, EntityType.PROJECT}

# Words with their trailing whitespace: diffing on these keeps spans
# readable (whole words move, never half of one) and re-concatenation
# lossless.
WORD_TOKENS = re.compile(r"\S+\s*|\s+")


def diff_spans(before: str, after: str) -> list[DiffSpan]:
    """The review diff: how 'after' differs from 'before', span by span.

    Deterministic by construction: concatenating the equal+insert spans
    rebuilds 'after' exactly, equal+delete rebuilds 'before'. A replace
    opcode becomes delete then insert, the reading order of a manager
    scanning 'what went away, what arrived'.
    """
    before_tokens = WORD_TOKENS.findall(before)
    after_tokens = WORD_TOKENS.findall(after)
    matcher = SequenceMatcher(None, before_tokens, after_tokens, autojunk=False)
    spans: list[DiffSpan] = []
    for op, before_lo, before_hi, after_lo, after_hi in matcher.get_opcodes():
        if op in ("delete", "replace"):
            spans.append(DiffSpan(op="delete", text="".join(before_tokens[before_lo:before_hi])))
        if op in ("insert", "replace"):
            spans.append(DiffSpan(op="insert", text="".join(after_tokens[after_lo:after_hi])))
        if op == "equal":
            spans.append(DiffSpan(op="equal", text="".join(after_tokens[after_lo:after_hi])))
    return spans


class EditingService:
    """Orchestrates the editing loop. Pure logic: all I/O behind seams."""

    def __init__(
        self,
        llm: LLMProvider,
        session_factory: sessionmaker[Session],
        darryl: DarrylService,
    ) -> None:
        """Wire the seams. darryl is the archivist the corpus entry
        goes through: the engine decides IF a document is filed, Darryl
        knows HOW."""
        self.llm = llm
        self.session_factory = session_factory
        self.darryl = darryl

    # --- persistence: the save gesture ---

    def create(self, payload: EditedDocumentCreate) -> EditedDocumentOut:
        """The first save: one generation becomes the manager's document.

        memory_reviewed_at starts at generated_at: the generation
        already gathered everything validated up to that moment, so
        'what's new' counts from there.
        """
        with self.session_factory() as session:
            document = EditedDocument(
                title=payload.title,
                template_key=payload.template_key,
                target_entity_type=payload.target_entity_type,
                target_entity_id=payload.target_entity_id,
                content_md=payload.content_md,
                generated_at=naive_utc(payload.generated_at),
                memory_reviewed_at=naive_utc(payload.generated_at),
            )
            session.add(document)
            session.commit()
            out = self._out(session, document)
        self._file_to_corpus(out)
        return out

    def save(self, document_id: int, payload: EditedDocumentUpdate) -> EditedDocumentOut:
        """A re-edit (manual or accepted revision): update the last state."""
        with self.session_factory() as session:
            document = self._get(session, document_id)
            document.content_md = payload.content_md
            document.updated_at = utcnow()
            session.commit()
            out = self._out(session, document)
        self._file_to_corpus(out)
        return out

    def get(self, document_id: int) -> EditedDocumentOut:
        """One document with its news badge."""
        with self.session_factory() as session:
            return self._out(session, self._get(session, document_id))

    def list_documents(self) -> list[EditedDocumentOut]:
        """Every persisted document, latest edit first, badges included."""
        with self.session_factory() as session:
            documents = session.scalars(
                select(EditedDocument).order_by(
                    EditedDocument.updated_at.desc(), EditedDocument.id.desc()
                )
            ).all()
            return [self._out(session, document) for document in documents]

    # --- the delta: what moved since the manager last looked ---

    def delta(self, document_id: int) -> DocumentDelta:
        """The proposals to triage: validated segments newer than the
        bookmark, about this document's target. Deterministic SQL, the
        same exhaustive philosophy as the summary gathering."""
        with self.session_factory() as session:
            document = self._get(session, document_id)
            segments = self._news(session, document)
            return DocumentDelta(
                document_id=document.id,
                segments=[
                    PamSource(
                        segment_id=segment.id,
                        entry_id=segment.entry_id,
                        content=segment.content,
                        data_type=segment.data_type,
                        sensitivity_level=segment.sensitivity_level,
                        created_at=segment.created_at,
                    )
                    for segment in segments
                ],
            )

    def mark_reviewed(self, document_id: int) -> EditedDocumentOut:
        """Advance the bookmark: the manager triaged the news.

        Dismissed for good BY DESIGN (owner, 2026-07-16): the segments
        stay in Pam's memory, they just stop knocking on this document.
        """
        with self.session_factory() as session:
            document = self._get(session, document_id)
            document.memory_reviewed_at = utcnow()
            session.commit()
            return self._out(session, document)

    # --- the revision: Dwight the pure reviser ---

    def revise(
        self, document_id: int, instruction: str, include_segment_ids: list[int]
    ) -> DocumentRevision:
        """One revision PROPOSAL: nothing is persisted here.

        The engine hands Dwight the current document, the instruction
        and the selected news excerpts - the context travels. The
        answer comes back with its computed diff; saving it is the
        caller's explicit next gesture.
        """
        with self.session_factory() as session:
            document = self._get(session, document_id)
            before = document.content_md
            material = []
            if include_segment_ids:
                selected = session.scalars(
                    select(EntrySegment).where(EntrySegment.id.in_(include_segment_ids))
                ).all()
                material = [
                    f"- ({segment.created_at:%Y-%m-%d}) {segment.content}"
                    for segment in selected
                ]
        try:
            revision = complete_validated(
                self.llm,
                build_revision_messages(before, instruction, material),
                DwightRevision,
            )
        except LLMContractError as exc:
            raise RevisionProcessingError(
                "Dwight could not produce a usable revision; try rewording."
            ) from exc
        return DocumentRevision(
            document_id=document_id,
            content_md=revision.content_md,
            diff=diff_spans(before, revision.content_md),
        )

    # --- building blocks ---

    @staticmethod
    def _get(session: Session, document_id: int) -> EditedDocument:
        """Fetch or raise: shared by every endpoint."""
        document = session.get(EditedDocument, document_id)
        if document is None:
            raise EditedDocumentNotFoundError(f"No edited document with id {document_id}.")
        return document

    @staticmethod
    def _news(session: Session, document: EditedDocument) -> list[EntrySegment]:
        """Validated segments about the target, newer than the bookmark.

        The segment's created_at is the proxy for 'when it entered the
        memory': validation has no timestamp of its own in the validated
        data model, and capture-to-validation is minutes in practice.
        Targetless documents (agenda, radar) have no delta: their
        template is the living view.
        """
        if document.target_entity_type is None or document.target_entity_id is None:
            return []
        return list(
            session.scalars(
                select(EntrySegment)
                .join(SegmentTag, SegmentTag.segment_id == EntrySegment.id)
                .where(
                    EntrySegment.validation_status == ValidationStatus.VALIDATED,
                    EntrySegment.created_at > document.memory_reviewed_at,
                    SegmentTag.entity_type == document.target_entity_type,
                    SegmentTag.entity_id == document.target_entity_id,
                )
                .distinct()
                .order_by(EntrySegment.created_at)
            ).all()
        )

    def _out(self, session: Session, document: EditedDocument) -> EditedDocumentOut:
        """Serialize one document with its news count."""
        out = EditedDocumentOut.model_validate(document)
        out.news_count = len(self._news(session, document))
        return out

    def _file_to_corpus(self, document: EditedDocumentOut) -> None:
        """Feed Darryl's corpus - client/project targets ONLY.

        The person exception (owner, 2026-07-16): a 1:1 brief or
        annual-review material stays on the Desk, out of Pam's memory.
        """
        if document.target_entity_type not in CORPUS_TARGETS:
            return
        if document.target_entity_id is None:
            return
        self.darryl.file_generated_document(
            title=document.title,
            text=document.content_md,
            origin_ref=f"scranton:{document.id}",
            entity_type=document.target_entity_type,
            entity_id=document.target_entity_id,
        )
