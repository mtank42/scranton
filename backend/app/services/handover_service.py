"""Transfer to Philly, case 1: the handover dossier and its consent trail.

Deterministic on purpose - NO LLM anywhere in this pipeline. A GDPR
consent artifact must carry the exact validated segments, verbatim,
never a model paraphrase. The service has no LLM seam and no vector
store: the dossier is relational truth only.

Two halves live here:
- the dossier: generation, selective disclosure, the portable contract;
- the consent trail (handover_validations, data model session
  2026-07-08): a strictly forward state machine, proposed ->
  employee_reviewed -> both_validated -> sent. The selection freezes
  when the member reviews it; a SHA-256 of the rendered markdown fiche
  freezes at signature time. Re-rendering the signed fiche later and
  comparing hashes is the tamper evidence: if the underlying segments
  changed since, the bytes (and the hash) no longer match.
"""

import hashlib
import json
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from backend.app.adapters.export.base import ExportFile
from backend.app.adapters.export.handover import HANDOVER_RENDERERS
from backend.app.domain.models import (
    Client,
    DataType,
    EntityType,
    EntrySegment,
    HandoverStatus,
    HandoverValidation,
    Project,
    SegmentTag,
    Stakeholder,
    TeamMember,
    ValidationStatus,
)
from backend.app.domain.schemas import (
    HandoverDossier,
    HandoverItem,
    HandoverValidationOut,
)
from backend.app.services.mood_service import MemberNotFoundError


class HandoverNotFoundError(LookupError):
    """No handover validation record with that id."""


class InvalidTransitionError(RuntimeError):
    """The consent record cannot reach that state from where it stands."""


class InvalidSelectionError(ValueError):
    """The disclosure selection names segments that are not disclosable."""


class ActiveHandoverExistsError(RuntimeError):
    """The member already has an open (not yet sent) handover."""

# The only legal moves of the consent state machine, strictly forward.
NEXT_STATUS = {
    HandoverStatus.PROPOSED: HandoverStatus.EMPLOYEE_REVIEWED,
    HandoverStatus.EMPLOYEE_REVIEWED: HandoverStatus.BOTH_VALIDATED,
    HandoverStatus.BOTH_VALIDATED: HandoverStatus.SENT,
}

# Entity tag -> table, for resolving human-readable topic labels.
ENTITY_TABLES = {
    EntityType.TEAM_MEMBER: TeamMember,
    EntityType.CLIENT: Client,
    EntityType.PROJECT: Project,
    EntityType.STAKEHOLDER: Stakeholder,
}


class HandoverService:
    """Assemble the dossier: cold block, sensitivity-sorted warm block."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        """Wire the only seam this service needs: the database."""
        self.session_factory = session_factory

    def dossier(
        self, member_id: int, *, include_warm: list[int] | None = None
    ) -> HandoverDossier:
        """Build the portable dossier for one member.

        include_warm is the manager's disclosure selection (warm segment
        ids). The two states matter and are distinct:
        - None: REVIEW state - every warm observation is shown so the
          manager can choose.
        - a list (possibly empty): DISCLOSURE state - only the named
          observations travel; an empty list withholds them all.
        Cold data is transmissible a priori and never filtered here.
        """
        with self.session_factory() as session:
            member = session.get(TeamMember, member_id)
            if member is None:
                raise MemberNotFoundError(f"No team member with id {member_id}.")

            segments = session.scalars(
                select(EntrySegment)
                .join(SegmentTag, SegmentTag.segment_id == EntrySegment.id)
                .where(
                    SegmentTag.entity_type == EntityType.TEAM_MEMBER,
                    SegmentTag.entity_id == member_id,
                    EntrySegment.validation_status == ValidationStatus.VALIDATED,
                )
                .distinct()
                .order_by(EntrySegment.created_at)
            ).all()
            labels = self._label_maps(session, segments)

            items = [
                HandoverItem(
                    segment_id=segment.id,
                    content=segment.content,
                    data_type=segment.data_type,
                    sensitivity_level=segment.sensitivity_level,
                    created_at=segment.created_at,
                    topics=self._topics(segment, labels),
                )
                for segment in segments
            ]

        cold = [item for item in items if item.data_type == DataType.COLD]
        # Sensitivity-sorted for review: the manager reads from benign to
        # delicate and decides where their disclosure stops.
        warm_all = sorted(
            (item for item in items if item.data_type == DataType.WARM),
            key=lambda item: (item.sensitivity_level, item.created_at),
        )
        if include_warm is None:
            warm = warm_all
        else:
            chosen = set(include_warm)
            warm = [item for item in warm_all if item.segment_id in chosen]

        return HandoverDossier(
            generated_at=datetime.now(timezone.utc),
            member_id=member_id,
            member_name=member.full_name,
            member_role=member.role,
            cold=cold,
            warm=warm,
            excluded_warm_count=len(warm_all) - len(warm),
        )

    @staticmethod
    def _label_maps(
        session: Session, segments: list[EntrySegment]
    ) -> dict[EntityType, dict[int, str]]:
        """Resolve every referenced entity name in one query per table.

        Batched on purpose: a dossier can carry hundreds of tags, and a
        per-tag lookup would be the classic silent N+1.
        """
        wanted: dict[EntityType, set[int]] = {kind: set() for kind in ENTITY_TABLES}
        for segment in segments:
            for tag in segment.tags:
                if tag.entity_id is not None and tag.entity_type in wanted:
                    wanted[tag.entity_type].add(tag.entity_id)
        labels: dict[EntityType, dict[int, str]] = {}
        for kind, ids in wanted.items():
            if not ids:
                labels[kind] = {}
                continue
            model = ENTITY_TABLES[kind]
            rows = session.scalars(select(model).where(model.id.in_(ids))).all()
            labels[kind] = {
                row.id: (getattr(row, "full_name", None) or row.name) for row in rows
            }
        return labels

    @staticmethod
    def _topics(
        segment: EntrySegment, labels: dict[EntityType, dict[int, str]]
    ) -> list[str]:
        """Human-readable routing labels for one segment."""
        topics = []
        for tag in segment.tags:
            if tag.view_type is not None:
                topics.append(f"view: {tag.view_type.value}")
            elif tag.entity_id is not None:
                label = labels.get(tag.entity_type, {}).get(tag.entity_id)
                if label:
                    topics.append(f"{tag.entity_type.value}: {label}")
        return topics

    # --- The consent trail (handover_validations) ---

    def validations(self, member_id: int) -> list[HandoverValidationOut]:
        """Every consent record for one member, newest first."""
        with self.session_factory() as session:
            if session.get(TeamMember, member_id) is None:
                raise MemberNotFoundError(f"No team member with id {member_id}.")
            records = session.scalars(
                select(HandoverValidation)
                .where(HandoverValidation.team_member_id == member_id)
                .order_by(
                    HandoverValidation.created_at.desc(),
                    HandoverValidation.id.desc(),
                )
            ).all()
            return [self._out(record) for record in records]

    def create_validation(
        self, member_id: int, *, disclosed_warm_ids: list[int]
    ) -> HandoverValidationOut:
        """Open a handover: status PROPOSED, selection still mutable.

        One open handover per member: a second consent thread about the
        same person would make 'what was agreed' ambiguous. Batch fiches
        are a case 2 (V2) topic, explicitly deferred.
        """
        ids = self._checked_selection(member_id, disclosed_warm_ids)
        with self.session_factory() as session:
            open_record = session.scalars(
                select(HandoverValidation).where(
                    HandoverValidation.team_member_id == member_id,
                    HandoverValidation.status != HandoverStatus.SENT,
                )
            ).first()
            if open_record is not None:
                raise ActiveHandoverExistsError(
                    f"Handover {open_record.id} is still open "
                    f"({open_record.status.value}): finish or send it first."
                )
            record = HandoverValidation(
                team_member_id=member_id, disclosed_warm_ids=json.dumps(ids)
            )
            session.add(record)
            session.commit()
            session.refresh(record)
            return self._out(record)

    def update_selection(
        self, validation_id: int, *, disclosed_warm_ids: list[int]
    ) -> HandoverValidationOut:
        """Change the selection - only while PROPOSED.

        Frozen from EMPLOYEE_REVIEWED on: the member reviewed THIS exact
        selection, so it cannot change under their upcoming signature.
        """
        with self.session_factory() as session:
            record = self._get(session, validation_id)
            if record.status is not HandoverStatus.PROPOSED:
                raise InvalidTransitionError(
                    "The selection is frozen once the member reviewed it "
                    f"(handover {validation_id} is {record.status.value})."
                )
            member_id = record.team_member_id
        ids = self._checked_selection(member_id, disclosed_warm_ids)
        with self.session_factory() as session:
            record = self._get(session, validation_id)
            record.disclosed_warm_ids = json.dumps(ids)
            session.commit()
            session.refresh(record)
            return self._out(record)

    def mark_reviewed(self, validation_id: int) -> HandoverValidationOut:
        """PROPOSED -> EMPLOYEE_REVIEWED: the member saw this exact selection."""
        with self.session_factory() as session:
            record = self._advance(session, validation_id, HandoverStatus.PROPOSED)
            record.reviewed_at = datetime.now(timezone.utc)
            session.commit()
            session.refresh(record)
            return self._out(record)

    def sign(
        self, validation_id: int, *, manager_name: str, member_name: str
    ) -> HandoverValidationOut:
        """EMPLOYEE_REVIEWED -> BOTH_VALIDATED: typed signatures, frozen hash.

        The SHA-256 covers the markdown fiche (the canonical artifact);
        signed_fiche() re-renders those exact bytes, so anyone can verify
        a downloaded fiche against the stored hash later.
        """
        # Read pass: state check + everything the renderer needs. The
        # fiche is rendered OUTSIDE any open session (dossier() opens its
        # own), then one single commit writes signatures + hash together.
        with self.session_factory() as session:
            record = self._get(session, validation_id)
            if record.status is not HandoverStatus.EMPLOYEE_REVIEWED:
                raise InvalidTransitionError(
                    f"Handover {validation_id} is {record.status.value}, "
                    "not employee_reviewed: cannot sign."
                )
            current = self._out(record)
        now = datetime.now(timezone.utc)
        signed_view = current.model_copy(
            update={
                "status": HandoverStatus.BOTH_VALIDATED,
                "manager_signature_name": manager_name,
                "manager_signed_at": now,
                "member_signature_name": member_name,
                "member_signed_at": now,
                "validated_at": now,
            }
        )
        digest = hashlib.sha256(self._render_fiche(signed_view, "md").content).hexdigest()
        with self.session_factory() as session:
            record = self._advance(
                session, validation_id, HandoverStatus.EMPLOYEE_REVIEWED
            )
            record.manager_signature_name = manager_name
            record.manager_signed_at = now
            record.member_signature_name = member_name
            record.member_signed_at = now
            record.validated_at = now
            record.fiche_sha256 = digest
            session.commit()
            session.refresh(record)
            return self._out(record)

    def mark_sent(self, validation_id: int) -> HandoverValidationOut:
        """BOTH_VALIDATED -> SENT: an explicit manager action, always.

        Never triggered by a download (owner decision, 2026-07-08): a
        download is a verification, a transmission is a decision.
        """
        with self.session_factory() as session:
            record = self._advance(
                session, validation_id, HandoverStatus.BOTH_VALIDATED
            )
            record.sent_at = datetime.now(timezone.utc)
            session.commit()
            session.refresh(record)
            return self._out(record)

    def signed_fiche(self, validation_id: int, *, format_key: str) -> ExportFile:
        """The signed artifact for download. Reads state, never changes it."""
        with self.session_factory() as session:
            record = self._get(session, validation_id)
            if record.status not in (
                HandoverStatus.BOTH_VALIDATED,
                HandoverStatus.SENT,
            ):
                raise InvalidTransitionError(
                    f"No signed fiche yet: handover {validation_id} is "
                    f"{record.status.value}."
                )
            out = self._out(record)
        return self._render_fiche(out, format_key)

    def _render_fiche(
        self, out: HandoverValidationOut, format_key: str
    ) -> ExportFile:
        """Render the frozen artifact from a consent view.

        generated_at is pinned to validated_at, so every render after
        signature reproduces the signed bytes exactly - that is what
        makes the stored SHA-256 verifiable. If the underlying segments
        were edited since, the bytes diverge and the hash exposes it.
        """
        dossier = self.dossier(
            out.team_member_id, include_warm=out.disclosed_warm_ids
        )
        dossier = dossier.model_copy(update={"generated_at": out.validated_at})
        return HANDOVER_RENDERERS[format_key](dossier, out)

    def _checked_selection(self, member_id: int, ids: list[int]) -> list[int]:
        """Normalize and vet a disclosure selection.

        Every id must be a disclosable warm segment of THIS member: a
        consent record must never reference something the member could
        not have reviewed. Raises MemberNotFoundError for ghosts.
        """
        wanted = sorted(set(ids))
        disclosable = {item.segment_id for item in self.dossier(member_id).warm}
        unknown = [wid for wid in wanted if wid not in disclosable]
        if unknown:
            raise InvalidSelectionError(
                f"Not disclosable warm segments of member {member_id}: {unknown}."
            )
        return wanted

    def _advance(
        self, session: Session, validation_id: int, expected: HandoverStatus
    ) -> HandoverValidation:
        """Guarded forward move: records advance one state at a time."""
        record = self._get(session, validation_id)
        if record.status is not expected:
            raise InvalidTransitionError(
                f"Handover {validation_id} is {record.status.value}, not "
                f"{expected.value}: cannot move to {NEXT_STATUS[expected].value}."
            )
        record.status = NEXT_STATUS[expected]
        return record

    @staticmethod
    def _get(session: Session, validation_id: int) -> HandoverValidation:
        """One consent record or a clean 404-grade error."""
        record = session.get(HandoverValidation, validation_id)
        if record is None:
            raise HandoverNotFoundError(
                f"No handover validation with id {validation_id}."
            )
        return record

    @staticmethod
    def _out(record: HandoverValidation) -> HandoverValidationOut:
        """ORM row -> API view, with the JSON selection decoded."""
        return HandoverValidationOut(
            id=record.id,
            team_member_id=record.team_member_id,
            status=record.status,
            disclosed_warm_ids=json.loads(record.disclosed_warm_ids),
            fiche_sha256=record.fiche_sha256,
            manager_signature_name=record.manager_signature_name,
            manager_signed_at=record.manager_signed_at,
            member_signature_name=record.member_signature_name,
            member_signed_at=record.member_signed_at,
            created_at=record.created_at,
            reviewed_at=record.reviewed_at,
            validated_at=record.validated_at,
            sent_at=record.sent_at,
        )
