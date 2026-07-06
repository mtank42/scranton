"""Tell Dwight: capture -> segment -> classify -> route -> validate.

The pipeline in one sentence: a raw note is persisted untouched, the LLM
proposes segments and routing, the manager validates, and only validated
segments are embedded into the vector store for Ask Pam.

Two deliberate design choices (both documented in docs/tell_dwight.md):
- Embedding happens at VALIDATION time, not capture time. The sketch
  suggested capture time, but indexing unvalidated proposals would let
  rejected content leak into Ask Pam's memory. Validation is the gate.
- A clarification does not open a dialogue. The vague entry stays as an
  immutable audit trail with status pending, and the manager submits a
  richer note as a new entry. Stateless, no conversation to persist.
"""

import json

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from backend.app.adapters.llm.base import LLMProvider
from backend.app.adapters.vectorstore.base import SegmentVector, VectorStore
from backend.app.domain.models import (
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
    SegmentOut,
)
from backend.app.services.prompts import RETRY_REMINDER, build_dwight_messages


class DwightProcessingError(Exception):
    """The LLM could not produce a usable proposal (after one retry)."""


class SegmentNotFoundError(Exception):
    """The requested segment id does not exist."""


def extract_json(text: str) -> dict:
    """Parse a JSON object out of an LLM answer, tolerating markdown fences.

    Small models sometimes wrap JSON in ```json fences despite explicit
    instructions. Stripping them here is cheaper and more reliable than
    prompt-engineering the habit away.
    """
    cleaned = text.strip()
    if cleaned.startswith("```"):
        # Drop the opening fence line (``` or ```json) and the closing fence.
        cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned
        cleaned = cleaned.rsplit("```", 1)[0].strip()
    return json.loads(cleaned)


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

    # --- capture ---

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

        proposal = self._propose(payload, routing_context)

        with self.session_factory() as session:
            entry = session.get(Entry, entry_id)
            if proposal.clarification:
                # Too vague: the entry stays pending as an audit trail and
                # the manager answers by submitting a richer note.
                return CaptureResponse(
                    entry_id=entry_id,
                    processing_status=entry.processing_status,
                    clarification=proposal.clarification,
                )
            for order, proposed in enumerate(proposal.segments):
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
            entry.processing_status = ProcessingStatus.COMPLETE
            session.commit()
            segments = [SegmentOut.model_validate(s) for s in entry.segments]
            return CaptureResponse(
                entry_id=entry_id,
                processing_status=entry.processing_status,
                segments=segments,
            )

    def _propose(self, payload: EntryCreate, routing_context: str) -> DwightProposal:
        """Call the LLM and parse its answer, with one formatting retry."""
        messages = build_dwight_messages(
            payload.raw_content, payload.source_type, routing_context
        )
        answer = self.llm.complete(messages)
        try:
            return DwightProposal.model_validate(extract_json(answer))
        except (json.JSONDecodeError, ValidationError):
            # One retry with the failed answer in context: cheap, and it
            # recovers most formatting slips from small models.
            retry_messages = messages + [
                {"role": "assistant", "content": answer},
                {"role": "user", "content": RETRY_REMINDER},
            ]
            answer = self.llm.complete(retry_messages)
            try:
                return DwightProposal.model_validate(extract_json(answer))
            except (json.JSONDecodeError, ValidationError) as exc:
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
        self, segment_id: int, status: ValidationStatus
    ) -> SegmentOut:
        """Record the manager's decision on one proposed segment.

        Validation is the gate to Ask Pam's memory: only a VALIDATED
        segment is embedded and indexed. A REJECTED segment stays in
        SQLite (audit trail) but never reaches the vector store.
        """
        with self.session_factory() as session:
            segment = session.get(EntrySegment, segment_id)
            if segment is None:
                raise SegmentNotFoundError(f"No segment with id {segment_id}.")
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
                            metadata=self._flatten_metadata(segment),
                        )
                    ]
                )
            session.commit()
            return SegmentOut.model_validate(segment)

    @staticmethod
    def _flatten_metadata(segment: EntrySegment) -> dict:
        """Build the Chroma metadata for one segment.

        Chroma metadata values must be scalars (no lists), so tags are
        flattened into boolean keys: 'team_member_3': True means 'tagged
        on team member 3'. Ask Pam (M2) filters on those keys.
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
