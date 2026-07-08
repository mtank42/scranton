"""Transfer to Philly, case 1: the handover dossier for one member.

Deterministic on purpose - NO LLM anywhere in this pipeline. A GDPR
consent artifact must carry the exact validated segments, verbatim,
never a model paraphrase. The service has no LLM seam and no vector
store: the dossier is relational truth only.

What ships now is the core: generation, selective disclosure, the
portable contract, the printable signable fiche. The validation
TRACEABILITY (the handover_validations table) requires a dedicated
data model session with the owner: the full proposal awaits in
docs/transfer_to_philly.md. Until then, the printed fiche carries a
two-party signature block - paper-level validation, deliberately.
"""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from backend.app.domain.models import (
    Client,
    DataType,
    EntityType,
    EntrySegment,
    Project,
    SegmentTag,
    Stakeholder,
    TeamMember,
    ValidationStatus,
)
from backend.app.domain.schemas import HandoverDossier, HandoverItem
from backend.app.services.mood_service import MemberNotFoundError

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
