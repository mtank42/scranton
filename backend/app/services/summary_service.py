"""Smart Summaries: the six living templates, Dwight + Pam together.

A summary is a LIVING DOCUMENT: computed from the validated memory at
request time, never stored. Three architectural choices carry this
module (docs/smart_summaries.md):

1. Gathering is EXHAUSTIVE SQL over segment tags, not vector top-k: a
   member file wants everything about the member, and semantic search
   would silently truncate it. Pam searches; summaries assemble.
2. Templates are DATA (the TEMPLATES registry below): adding the
   seventh template means describing it, not writing new code paths.
3. Only VALIDATED segments feed a summary - the same single gate as
   Ask Pam and Meet Toby.
"""

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from backend.app.adapters.llm.base import LLMProvider
from backend.app.domain.models import (
    MOOD_INDEX,
    Client,
    DataType,
    EntityType,
    EntrySegment,
    MoodCheckin,
    Project,
    SegmentTag,
    TeamMember,
    ValidationStatus,
    ViewType,
)
from backend.app.domain.schemas import (
    LLMSummary,
    PamSource,
    SummaryCatalog,
    SummaryResponse,
    SummarySection,
    SummaryTemplateInfo,
    TargetOption,
)
from backend.app.services.llm_json import LLMContractError, complete_validated
from backend.app.services.mood_service import utc_cutoff
from backend.app.services.prompts import build_summary_messages

# A summary call stays affordable: beyond this many excerpts, the most
# recent win and the context says so.
MAX_EXCERPTS = 60

NO_MATERIAL_LINE = "Nothing recorded yet."


class UnknownTemplateError(Exception):
    """No template with that id in the registry."""


class TargetRequiredError(Exception):
    """This template needs a target id and none was given."""


class TargetNotFoundError(Exception):
    """The target id does not match a known entity."""


class SummaryProcessingError(Exception):
    """The model could not produce a valid summary (after one retry)."""


@dataclass(frozen=True)
class SummaryTemplate:
    """One living template: what it is about and which sections it fills."""

    id: str
    title: str
    description: str
    # team_member | project | client, or None for team-wide templates.
    target: str | None
    sections: tuple[str, ...]
    # Default lookback; None means the whole history.
    window_days: int | None
    # Which view tags to gather (for templates driven by views rather
    # than by an entity). Empty means: gather by the target entity.
    views: tuple[ViewType, ...] = ()
    # Extra context switches (mood data, human profile).
    include_moods: bool = False
    include_profile: bool = False


TEMPLATES: dict[str, SummaryTemplate] = {
    template.id: template
    for template in (
        SummaryTemplate(
            id="team_member_file",
            # 'file' is banned from the UI vocabulary (owner, recadrage
            # 2026-07-12); ids stay technical identifiers, titles are UI.
            title="Team Member",
            description="Skills, history, observations and signals for one member.",
            target="team_member",
            sections=(
                "Role and skills",
                "History and contributions",
                "Manager observations",
                "Signals to watch",
            ),
            window_days=None,
            include_moods=True,
            include_profile=True,
        ),
        SummaryTemplate(
            id="project_file",
            title="Project",
            description="Decisions, deliverables, people and open points of a project.",
            target="project",
            sections=(
                "Status and decisions",
                "Deliverables and dates",
                "People involved",
                "Open points",
            ),
            window_days=None,
        ),
        SummaryTemplate(
            id="client_file",
            title="Client",
            description="Relationship history, preferences, commitments and activity.",
            target="client",
            sections=(
                "Relationship history",
                "Preferences and constraints",
                "Commitments made",
                "Recent activity",
            ),
            window_days=None,
        ),
        SummaryTemplate(
            id="meeting_agenda",
            title="Meeting Agenda",
            description="What to bring up next time: topics, commitments, follow-ups.",
            target=None,
            sections=("Topics to raise", "Pending commitments", "Follow-ups"),
            window_days=30,
            views=(ViewType.MEETING_AGENDA, ViewType.MEETING_CR, ViewType.COMMITMENT),
        ),
        SummaryTemplate(
            id="team_radar",
            title="Team Radar",
            description="The manager 360: mood, weak signals, load and balance.",
            target=None,
            sections=(
                "Team mood",
                "Weak signals",
                "Load and balance",
                "Facts to keep in mind",
            ),
            window_days=30,
            include_moods=True,
        ),
        SummaryTemplate(
            id="annual_review",
            title="Annual Review Material",
            description="A year of facts and discussion points - material, never a verdict.",
            target="team_member",
            sections=(
                "Year in facts",
                "Growth and skills",
                "Contributions",
                "Points for discussion",
            ),
            window_days=365,
            include_moods=True,
            include_profile=True,
        ),
    )
}

# Target kind -> (entity table, EntityType tag value).
TARGET_KINDS = {
    "team_member": (TeamMember, EntityType.TEAM_MEMBER),
    "project": (Project, EntityType.PROJECT),
    "client": (Client, EntityType.CLIENT),
}


class SummaryService:
    """Gather exhaustively, synthesize once, return sections + sources."""

    def __init__(
        self, llm: LLMProvider, session_factory: sessionmaker[Session]
    ) -> None:
        """Wire the two seams the engine needs (no vector store here)."""
        self.llm = llm
        self.session_factory = session_factory

    # --- catalog ---

    def catalog(self) -> SummaryCatalog:
        """The templates and every pickable target, in one call for the UI."""
        with self.session_factory() as session:
            targets = {
                kind: [
                    TargetOption(
                        id=row.id,
                        name=getattr(row, "full_name", None) or row.name,
                    )
                    for row in session.scalars(select(model)).all()
                    if getattr(row, "is_active", True)
                ]
                for kind, (model, _) in TARGET_KINDS.items()
            }
        return SummaryCatalog(
            templates=[
                SummaryTemplateInfo(
                    id=template.id,
                    title=template.title,
                    description=template.description,
                    target=template.target,
                    window_days=template.window_days,
                )
                for template in TEMPLATES.values()
            ],
            targets=targets,
        )

    # --- generation ---

    def generate(self, template_id: str, target_id: int | None = None) -> SummaryResponse:
        """Build one living summary from the validated memory."""
        template = TEMPLATES.get(template_id)
        if template is None:
            raise UnknownTemplateError(f"No summary template named {template_id!r}.")

        with self.session_factory() as session:
            target_label = self._resolve_target(session, template, target_id)
            segments = self._gather(session, template, target_id)
            sources = [
                PamSource(
                    segment_id=segment.id,
                    entry_id=segment.entry_id,
                    content=segment.content,
                    data_type=segment.data_type,
                    sensitivity_level=segment.sensitivity_level,
                    created_at=segment.created_at,
                )
                for segment in segments
            ]
            extra_context = self._extra_context(session, template, target_id)

        if not sources and not extra_context:
            # Honest and free: no material means an empty file, not an
            # invented one - and zero completion tokens.
            return self._empty_summary(template, target_label)

        context_lines = [
            f"[{i}] ({source.created_at:%Y-%m-%d}) {source.content}"
            for i, source in enumerate(sources, start=1)
        ]
        if len(sources) == MAX_EXCERPTS:
            context_lines.append(
                f"(note: only the {MAX_EXCERPTS} most recent excerpts are shown)"
            )
        context_lines.extend(extra_context)

        messages = build_summary_messages(
            template.title, target_label, template.sections, "\n".join(context_lines)
        )
        try:
            summary = complete_validated(self.llm, messages, LLMSummary)
        except LLMContractError as exc:
            raise SummaryProcessingError(
                f"The model could not fill the {template.title} template; try again."
            ) from exc

        return SummaryResponse(
            template_id=template.id,
            title=template.title,
            target_label=target_label,
            generated_at=datetime.now(timezone.utc),
            window_days=template.window_days,
            sections=summary.sections,
            sources=sources,
        )

    # --- building blocks ---

    @staticmethod
    def _resolve_target(
        session: Session, template: SummaryTemplate, target_id: int | None
    ) -> str | None:
        """Validate the target requirement and return its display label."""
        if template.target is None:
            return None
        if target_id is None:
            raise TargetRequiredError(
                f"{template.title} needs a {template.target} id (target_id)."
            )
        model, _ = TARGET_KINDS[template.target]
        row = session.get(model, target_id)
        if row is None:
            raise TargetNotFoundError(f"No {template.target} with id {target_id}.")
        return getattr(row, "full_name", None) or row.name

    @staticmethod
    def _gather(
        session: Session, template: SummaryTemplate, target_id: int | None
    ) -> list[EntrySegment]:
        """Exhaustive, chronological, validated-only segment collection."""
        query = (
            select(EntrySegment)
            .join(SegmentTag, SegmentTag.segment_id == EntrySegment.id)
            .where(EntrySegment.validation_status == ValidationStatus.VALIDATED)
            .distinct()
        )
        if template.views:
            query = query.where(SegmentTag.view_type.in_(template.views))
        elif template.target is not None:
            _, entity_type = TARGET_KINDS[template.target]
            query = query.where(
                SegmentTag.entity_type == entity_type,
                SegmentTag.entity_id == target_id,
            )
        elif template.include_moods:
            # Team radar: the narrative material is the warm layer.
            query = query.where(EntrySegment.data_type == DataType.WARM)
        if template.window_days is not None:
            query = query.where(
                EntrySegment.created_at >= utc_cutoff(template.window_days)
            )
        # Most recent first for the cap, then back to chronological so
        # the model reads the story in order.
        segments = session.scalars(
            query.order_by(EntrySegment.created_at.desc()).limit(MAX_EXCERPTS)
        ).all()
        return sorted(segments, key=lambda segment: segment.created_at)

    @staticmethod
    def _extra_context(
        session: Session, template: SummaryTemplate, target_id: int | None
    ) -> list[str]:
        """Non-segment context lines: mood data, human profile."""
        lines: list[str] = []
        if template.include_profile and target_id is not None:
            member = session.get(TeamMember, target_id)
            if member is not None and member.personal_profile:
                lines.append(
                    "(member-owned human profile, context only: "
                    f"{member.personal_profile})"
                )
        if template.include_moods:
            window = template.window_days or 30
            query = (
                select(MoodCheckin)
                .where(MoodCheckin.created_at >= utc_cutoff(window))
                .order_by(MoodCheckin.created_at)
            )
            if template.target == "team_member" and target_id is not None:
                query = query.where(MoodCheckin.team_member_id == target_id)
            checkins = session.scalars(query).all()
            if checkins:
                indexes = [MOOD_INDEX[checkin.mood_level] for checkin in checkins]
                path = " -> ".join(checkin.mood_level.value for checkin in checkins[-6:])
                lines.append(
                    f"(mood data, last {window} days: {len(checkins)} check-ins, "
                    f"average palette index {sum(indexes) / len(indexes):.1f}/5, "
                    f"recent path: {path})"
                )
        return lines

    @staticmethod
    def _empty_summary(
        template: SummaryTemplate, target_label: str | None
    ) -> SummaryResponse:
        """Every section honestly empty, no model call."""
        return SummaryResponse(
            template_id=template.id,
            title=template.title,
            target_label=target_label,
            generated_at=datetime.now(timezone.utc),
            window_days=template.window_days,
            sections=[
                SummarySection(heading=heading, content=NO_MATERIAL_LINE)
                for heading in template.sections
            ],
            sources=[],
        )
