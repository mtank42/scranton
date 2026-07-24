"""Tell Dwight: capture -> segment -> classify -> route -> validate.

The pipeline in one sentence: a raw note is persisted untouched, the LLM
proposes segments and routing, the manager validates, and only validated
segments are embedded into the vector store for Ask Pam.

Design decisions (documented in docs/tell_dwight.md):
- Embedding happens at VALIDATION time, not capture time: validation is
  the gate to Ask Pam's memory.
- The dialogue (clarification answers, rework comments) is NOT persisted
  as a thread (owner decision, 2026-07-06): only the raw note and the
  resulting segments count. Dialogue text feeds the model transiently.
- A rejected segment stays in SQLite as audit trail. A rework rejects
  the old proposal and adds a corrected one at the same position; the
  loop runs until the manager validates or bails out ('Forget it' is a
  plain reject through the validate endpoint).
"""

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from backend.app.adapters.llm.base import LLMProvider
from backend.app.adapters.vectorstore.base import SegmentVector, VectorStore
from backend.app.domain.models import (
    BIRTHDAY_YEAR,
    Client,
    Entry,
    EntrySegment,
    ProcessingStatus,
    Project,
    ProposedBy,
    SegmentTag,
    Stakeholder,
    TeamMember,
    ValidationStatus,
)
from backend.app.domain.schemas import (
    CaptureResponse,
    DwightProposal,
    EntryCreate,
    EntryHistoryOut,
    ProposedSegment,
    SegmentOut,
)
from backend.app.services.llm_json import (
    LLMContractError,
    complete_validated,
    extract_json,  # noqa: F401  (re-exported: tests and callers import it here)
)
from backend.app.services.prompts import build_dwight_messages, build_rework_messages


class DwightProcessingError(Exception):
    """The LLM could not produce a usable proposal (after one retry)."""


class SegmentNotFoundError(Exception):
    """The requested segment id does not exist."""


class EntryNotFoundError(Exception):
    """The requested entry id does not exist."""


class EntryNotPendingError(Exception):
    """The entry is not awaiting clarification: nothing to reply to."""


class NotYourEntryError(Exception):
    """The emitter validation doctrine, enforced: each person submits
    and decides THEIR OWN entries (day-one data model,
    entries.submitted_by_id; live since the identity session). Not
    even the manager decides someone else's proposals - the gate to
    the shared memory belongs to whoever wrote the note."""


class SegmentNotProposedError(Exception):
    """The segment was already decided: only proposals can be reworked."""


def flatten_segment_metadata(segment: EntrySegment) -> dict:
    """Build the Chroma metadata for one segment.

    Chroma metadata values must be scalars (no lists), so tags are
    flattened into boolean keys: 'team_member_3': True means 'tagged on
    team member 3'. Ask Pam filters on those keys. Shared by the live
    pipeline and the demo seeder so both index the exact same shape.
    """
    metadata: dict = {
        "segment_id": segment.id,
        "entry_id": segment.entry_id,
        "data_type": segment.data_type.value,
        "sensitivity_level": segment.sensitivity_level,
    }
    for tag in segment.tags:
        if tag.view_type is not None:
            metadata[f"view_{tag.view_type.value}"] = True
        elif tag.entity_id is not None:
            metadata[f"{tag.entity_type.value}_{tag.entity_id}"] = True
    return metadata


class DwightService:
    """Orchestrates the capture pipeline. Pure logic: all I/O behind seams."""

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

    # --- capture and clarification dialogue ---

    def capture(self, payload: EntryCreate) -> CaptureResponse:
        """Run one raw note through the full pipeline.

        The raw entry is committed BEFORE the LLM call: if the model call
        fails, nothing human is lost - the note is safe with status
        pending and can be reprocessed later.
        """
        with self.session_factory() as session:
            entry = Entry(
                raw_content=payload.raw_content,
                source_type=payload.source_type,
                submitted_by_id=payload.submitted_by_id,
            )
            session.add(entry)
            session.commit()
            entry_id = entry.id
            routing_context = self._build_routing_context(session)

        proposal = self._complete_proposal(
            build_dwight_messages(payload.raw_content, payload.source_type, routing_context)
        )
        return self._finalize(entry_id, proposal)

    def reply(
        self, entry_id: int, message: str, *, emitter_id: int | None = None
    ) -> CaptureResponse:
        """Continue the clarification dialogue on a pending entry.

        The emitter's answer is folded into the reprocessing context
        transiently; if Dwight is still unsure, another clarification
        comes back and the thread continues. emitter_id is the
        session's team_member_id (None = the manager): only the
        entry's author continues its dialogue.
        """
        with self.session_factory() as session:
            entry = session.get(Entry, entry_id)
            if entry is None:
                raise EntryNotFoundError(f"No entry with id {entry_id}.")
            self._ensure_emitter(entry, emitter_id)
            if entry.processing_status != ProcessingStatus.PENDING:
                raise EntryNotPendingError(
                    f"Entry {entry_id} is not awaiting clarification."
                )
            raw_content = entry.raw_content
            source_type = entry.source_type
            routing_context = self._build_routing_context(session)

        augmented = (
            f"{raw_content}\n\n"
            "[Additional context from the manager, answering your clarifying question]\n"
            f"{message}"
        )
        proposal = self._complete_proposal(
            build_dwight_messages(augmented, source_type, routing_context)
        )
        return self._finalize(entry_id, proposal)

    def _finalize(self, entry_id: int, proposal: DwightProposal) -> CaptureResponse:
        """Persist a proposal (or return the clarifying question)."""
        with self.session_factory() as session:
            entry = session.get(Entry, entry_id)
            if proposal.clarification:
                # Too vague: the entry stays pending as an audit trail and
                # the dialogue continues through the reply endpoint.
                return CaptureResponse(
                    entry_id=entry_id,
                    processing_status=entry.processing_status,
                    clarification=proposal.clarification,
                )
            for order, proposed in enumerate(proposal.segments):
                self._add_segment(session, entry_id, proposed, order)
            entry.processing_status = ProcessingStatus.COMPLETE
            session.commit()
            segments = [SegmentOut.model_validate(s) for s in entry.segments]
            return CaptureResponse(
                entry_id=entry_id,
                processing_status=entry.processing_status,
                segments=segments,
                profile_suggestions=self._resolve_suggestions(
                    session, proposal, entry.raw_content
                ),
                # Personal-life info was left out AND said out loud (owner,
                # QA 2026-07-14): the acknowledgment rides along, nothing
                # about it is ever persisted.
                privacy_note=proposal.privacy_note,
            )

    @staticmethod
    def _resolve_suggestions(
        session: Session, proposal: DwightProposal, raw_content: str
    ) -> list:
        """Attach member names to profile suggestions, drop unknown ids.

        Suggestions are transient (never persisted): adding one to a
        profile is an explicit manager action on the team endpoints.
        Two guards apply:
        - Closed world: a suggestion about a member the roster does not
          know is silently discarded.
        - Year erasure: a birthday is an event (day + month), never an
          age. Whatever year the model emits - real or invented, it
          cannot tell the difference - is normalized to BIRTHDAY_YEAR
          and never shown (owner decision, 2026-07-06).
        """
        resolved = []
        for suggestion in proposal.profile_suggestions:
            member = session.get(TeamMember, suggestion.team_member_id)
            if member is None or not member.is_active:
                continue
            if suggestion.birthday:
                suggestion.birthday = suggestion.birthday.replace(year=BIRTHDAY_YEAR)
            suggestion.member_name = member.full_name
            resolved.append(suggestion)
        return resolved

    # --- rework loop ---

    def rework(
        self, segment_id: int, comment: str, *, emitter_id: int | None = None
    ) -> SegmentOut:
        """Reject a proposed segment and get a corrected replacement.

        The rejected row stays as audit trail; the replacement arrives
        as a new proposal at the same position. The emitter can rework
        again, validate, or bail out with a plain reject.
        """
        with self.session_factory() as session:
            segment = session.get(EntrySegment, segment_id)
            if segment is None:
                raise SegmentNotFoundError(f"No segment with id {segment_id}.")
            self._ensure_emitter(segment.entry, emitter_id)
            if segment.validation_status != ValidationStatus.PROPOSED:
                raise SegmentNotProposedError(
                    f"Segment {segment_id} was already decided: rework applies to proposals."
                )
            raw_content = segment.entry.raw_content
            rejected_content = segment.content
            entry_id = segment.entry_id
            order = segment.segment_order
            routing_context = self._build_routing_context(session)
            segment.validation_status = ValidationStatus.REJECTED
            for tag in segment.tags:
                tag.validated = False
            session.commit()

        proposal = self._complete_proposal(
            build_rework_messages(raw_content, rejected_content, comment, routing_context)
        )
        if not proposal.segments:
            raise DwightProcessingError(
                "Dwight could not produce a corrected segment; the rejection is recorded."
            )
        with self.session_factory() as session:
            replacement = self._add_segment(session, entry_id, proposal.segments[0], order)
            session.commit()
            return SegmentOut.model_validate(replacement)

    # --- shared building blocks ---

    @staticmethod
    def _ensure_emitter(entry: Entry, emitter_id: int | None) -> None:
        """Refuse any gesture on someone else's entry (emitter doctrine).

        emitter_id is the session's team_member_id, None for the
        manager; entries store the same shape in submitted_by_id.
        """
        if entry.submitted_by_id != emitter_id:
            raise NotYourEntryError(
                "This note belongs to its author: only they decide on it."
            )

    @staticmethod
    def _add_segment(
        session: Session, entry_id: int, proposed: ProposedSegment, order: int
    ) -> EntrySegment:
        """Persist one proposed segment and its tags (status: proposed)."""
        segment = EntrySegment(
            entry_id=entry_id,
            content=proposed.content,
            segment_order=order,
            data_type=proposed.data_type,
            sensitivity_level=proposed.sensitivity_level,
        )
        session.add(segment)
        session.flush()
        for tag in proposed.tags:
            session.add(
                SegmentTag(
                    segment_id=segment.id,
                    entity_type=tag.entity_type,
                    entity_id=tag.entity_id,
                    view_type=tag.view_type,
                    proposed_by=ProposedBy.DWIGHT,
                    confidence=tag.confidence,
                )
            )
        return segment

    def _complete_proposal(self, messages: list[dict]) -> DwightProposal:
        """Call the LLM through the shared JSON contract (one retry inside)."""
        try:
            return complete_validated(self.llm, messages, DwightProposal)
        except LLMContractError as exc:
            raise DwightProcessingError(
                "Dwight could not produce a valid proposal for this note. "
                "The raw entry is saved (status pending); try again later."
            ) from exc

    def _build_routing_context(self, session: Session) -> str:
        """Format the known entities for the prompt, one line per entity.

        Dwight may only reference these ids in entity tags: giving the
        model the actual roster is what turns free text into routed data.
        """
        lines: list[str] = []
        members = session.scalars(
            select(TeamMember).where(TeamMember.is_active.is_(True))
        ).all()
        lines.append("team_members: " + self._format_entities(members))
        lines.append("clients: " + self._format_entities(session.scalars(select(Client)).all()))
        lines.append("projects: " + self._format_entities(session.scalars(select(Project)).all()))
        lines.append(
            "stakeholders: " + self._format_entities(session.scalars(select(Stakeholder)).all())
        )
        return "\n".join(lines)

    @staticmethod
    def _format_entities(rows: list) -> str:
        """Render entity rows as 'id=N name' pairs, or an explicit 'none'."""
        if not rows:
            return "(none)"
        names = []
        for row in rows:
            label = getattr(row, "full_name", None) or getattr(row, "name", "")
            names.append(f"id={row.id} {label}")
        return "; ".join(names)

    # --- validation ---

    def validate_segment(
        self,
        segment_id: int,
        status: ValidationStatus,
        *,
        emitter_id: int | None = None,
    ) -> SegmentOut:
        """Record the emitter's decision on one proposed segment.

        Validation is the gate to Ask Pam's memory: only a VALIDATED
        segment is embedded and indexed. A REJECTED segment stays in
        SQLite (audit trail) but never reaches the vector store. The
        gate belongs to whoever wrote the note (emitter validation,
        day-one doctrine): emitter_id must match the entry's author.
        """
        with self.session_factory() as session:
            segment = session.get(EntrySegment, segment_id)
            if segment is None:
                raise SegmentNotFoundError(f"No segment with id {segment_id}.")
            self._ensure_emitter(segment.entry, emitter_id)
            segment.validation_status = status
            for tag in segment.tags:
                tag.validated = status == ValidationStatus.VALIDATED
            if status == ValidationStatus.VALIDATED:
                embedding = self.llm.embed([segment.content])[0]
                self.vector_store.upsert(
                    [
                        SegmentVector(
                            segment_id=segment.id,
                            embedding=embedding,
                            metadata=flatten_segment_metadata(segment),
                        )
                    ]
                )
            session.commit()
            return SegmentOut.model_validate(segment)

    # --- history ---

    def history(
        self,
        limit: int = 5,
        offset: int = 0,
        *,
        emitter_id: int | None = None,
    ) -> list[EntryHistoryOut]:
        """Past notes, newest first: the Pam overlay history strip.

        Until now the Dwight thread was per session (nothing survived a
        reload); this is the durable trail the owner asked for
        (2026-07-15). Scoped to ONE emitter (the session's identity):
        your thread shows your notes - the shared memory only ever
        receives what each author validated. Counting segments in
        Python is fine at strip scale: the page is 5 to 15 rows, each
        with a handful of segments already loaded by the relationship.
        """
        with self.session_factory() as session:
            entries = session.scalars(
                select(Entry)
                .where(
                    Entry.submitted_by_id.is_(None)
                    if emitter_id is None
                    else Entry.submitted_by_id == emitter_id
                )
                .order_by(Entry.created_at.desc(), Entry.id.desc())
                .limit(limit)
                .offset(offset)
            ).all()
            return [
                EntryHistoryOut(
                    id=entry.id,
                    raw_content=entry.raw_content,
                    source_type=entry.source_type,
                    created_at=entry.created_at,
                    segments_total=len(entry.segments),
                    segments_validated=sum(
                        1
                        for segment in entry.segments
                        if segment.validation_status == ValidationStatus.VALIDATED
                    ),
                )
                for entry in entries
            ]
