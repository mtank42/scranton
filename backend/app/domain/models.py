"""SQLAlchemy ORM mapping of the validated Scranton data model.

These eight tables are a direct mapping of the data model validated in
May 2026 (SCRANTON_CONTEXT.md section 5). The model is frozen: do not
add, remove or rename fields without a dedicated session with the owner.

Two design principles are baked into the schema and must survive here:
- Raw entries are immutable: only segments are processed and routed.
- The cold/warm distinction and the sensitivity level live at the segment
  level (not the entry level), because a single note can mix objective
  facts with sensitive personal observations.
"""

import enum
from datetime import date, datetime, timezone

from sqlalchemy import CheckConstraint, ForeignKey, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    """Timezone-aware UTC now: naive datetimes are a classic source of bugs."""
    return datetime.now(timezone.utc)


def as_db_enum(enum_class: type[enum.Enum]) -> SAEnum:
    """Map a Python enum to a string column storing the enum values.

    By default SQLAlchemy stores member names (e.g. 'NOTE'); we want the
    lowercase values documented in the data model (e.g. 'note') so the
    database stays readable on its own, without the Python code around.
    """
    return SAEnum(
        enum_class,
        values_callable=lambda cls: [member.value for member in cls],
        native_enum=False,
    )


# --- Controlled vocabularies (values documented in SCRANTON_CONTEXT.md) ---


class SourceType(str, enum.Enum):
    """Where a raw entry came from (entries.source_type)."""

    NOTE = "note"
    MEETING_CR = "meeting_cr"
    DELIVERABLE = "deliverable"
    QUOTE = "quote"
    PURCHASE_ORDER = "purchase_order"
    CHAT = "chat"
    TRANSCRIPT = "transcript"
    VOICE_NOTE = "voice_note"


class ProcessingStatus(str, enum.Enum):
    """Lifecycle of a raw entry through the Tell Dwight pipeline."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETE = "complete"


class DataType(str, enum.Enum):
    """Cold: objective fact. Warm: subjective manager observation.

    Native at the segment level from day one, because Transfer to Philly
    (V1) discloses cold and warm data under different rules.
    """

    COLD = "cold"
    WARM = "warm"


class ValidationStatus(str, enum.Enum):
    """Emitter validation of a proposed segment.

    In the POC the single manager validates everything; in V2 each team
    member validates their own submissions.
    """

    PROPOSED = "proposed"
    VALIDATED = "validated"
    REJECTED = "rejected"


class EntityType(str, enum.Enum):
    """What a segment tag points at."""

    CLIENT = "client"
    PROJECT = "project"
    TEAM_MEMBER = "team_member"
    STAKEHOLDER = "stakeholder"
    VIEW = "view"


class ViewType(str, enum.Enum):
    """The ten views a segment can feed (set only when entity_type is VIEW)."""

    TEAM_MEMBER_FILE = "team_member_file"
    PROJECT_FILE = "project_file"
    CLIENT_FILE = "client_file"
    MEETING_AGENDA = "meeting_agenda"
    MEETING_CR = "meeting_cr"
    ANNUAL_REVIEW = "annual_review"
    IDEA_BOX = "idea_box"
    TEAM_RADAR = "team_radar"
    COMMITMENT = "commitment"
    RETROSPECTIVE = "retrospective"


class ProposedBy(str, enum.Enum):
    """Who proposed a tag: Dwight (the LLM) or the manager."""

    DWIGHT = "dwight"
    MANAGER = "manager"


class RelationshipType(str, enum.Enum):
    """How a stakeholder relates to the team."""

    PARTNER = "partner"
    SUBCONTRACTOR = "subcontractor"
    INVESTOR = "investor"
    SECONDARY_CONTACT = "secondary_contact"
    INSTITUTIONAL = "institutional"


class MoodLevel(str, enum.Enum):
    """The six-level Pretzel Day palette, from flow to danger."""

    FLOW = "flow"
    CTRL = "ctrl"
    PRETZEL_DAY = "pretzel_day"
    PRESS = "press"
    STUCK = "stuck"
    DANGER = "danger"


# --- The eight tables ---


class Base(DeclarativeBase):
    """Declarative base shared by the eight tables."""


class TeamMember(Base):
    """Team roster. Departures flip is_active: rows are never deleted."""

    __tablename__ = "team_members"

    id: Mapped[int] = mapped_column(primary_key=True)
    full_name: Mapped[str] = mapped_column(String(120))
    role: Mapped[str | None] = mapped_column(String(120))
    is_active: Mapped[bool] = mapped_column(default=True)
    # Owned by the team member (data ownership split). Used by Ask Pam for
    # the Maire de Scranton ritual and manager reminders (V1).
    birthday: Mapped[date | None]
    # Free text for now (a structured table is an open V1 question). Owned
    # by the team member: the manager only enters it on their behalf in the
    # POC because there is no auth yet.
    personal_profile: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class Entry(Base):
    """Raw input received by Tell Dwight.

    Immutable after creation: Dwight reformulates and routes segments,
    never the original text. raw_content is the audit trail.
    """

    __tablename__ = "entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    raw_content: Mapped[str] = mapped_column(Text)
    source_type: Mapped[SourceType] = mapped_column(as_db_enum(SourceType))
    # Null means the manager submitted directly. A value anticipates V2
    # multi-user, where team members submit (and validate) their own entries.
    submitted_by_id: Mapped[int | None] = mapped_column(ForeignKey("team_members.id"))
    processing_status: Mapped[ProcessingStatus] = mapped_column(
        as_db_enum(ProcessingStatus), default=ProcessingStatus.PENDING
    )
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    segments: Mapped[list["EntrySegment"]] = relationship(
        back_populates="entry",
        cascade="all, delete-orphan",
        order_by="EntrySegment.segment_order",
    )


class EntrySegment(Base):
    """Dwight's output: one reformulated, classified chunk of an entry.

    This is the real data layer: everything downstream (Ask Pam retrieval,
    views, exports) consumes segments, never raw entries.
    """

    __tablename__ = "entry_segments"
    __table_args__ = (
        CheckConstraint("sensitivity_level BETWEEN 1 AND 5", name="ck_sensitivity_range"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    entry_id: Mapped[int] = mapped_column(ForeignKey("entries.id"))
    content: Mapped[str] = mapped_column(Text)
    # Position of this chunk within its source entry.
    segment_order: Mapped[int]
    data_type: Mapped[DataType] = mapped_column(as_db_enum(DataType))
    # 1: objective fact, 5: highly sensitive personal observation. Drives
    # selective disclosure in Transfer to Philly (V1).
    sensitivity_level: Mapped[int]
    validation_status: Mapped[ValidationStatus] = mapped_column(
        as_db_enum(ValidationStatus), default=ValidationStatus.PROPOSED
    )
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    entry: Mapped[Entry] = relationship(back_populates="segments")
    tags: Mapped[list["SegmentTag"]] = relationship(
        back_populates="segment", cascade="all, delete-orphan"
    )


class SegmentTag(Base):
    """Multi-dimensional routing: one row per tag per segment.

    A single segment can feed a project file, a team member file and a
    view at the same time: that is the whole point of capture-once.
    """

    __tablename__ = "segment_tags"
    __table_args__ = (
        CheckConstraint("confidence >= 0.0 AND confidence <= 1.0", name="ck_confidence_range"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    segment_id: Mapped[int] = mapped_column(ForeignKey("entry_segments.id"))
    entity_type: Mapped[EntityType] = mapped_column(as_db_enum(EntityType))
    # Nullable on purpose: a 'view' tag points at a view_type, not a row.
    entity_id: Mapped[int | None]
    view_type: Mapped[ViewType | None] = mapped_column(as_db_enum(ViewType))
    proposed_by: Mapped[ProposedBy] = mapped_column(as_db_enum(ProposedBy))
    # Dwight's confidence in this routing, 0 to 1. Low confidence is how
    # the UI knows to ask the manager instead of silently assuming.
    confidence: Mapped[float]
    validated: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    segment: Mapped[EntrySegment] = relationship(back_populates="tags")


class Client(Base):
    """Client entities, referenced by segment tags and project files."""

    __tablename__ = "clients"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class Project(Base):
    """Project entities, optionally linked to a client."""

    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    client_id: Mapped[int | None] = mapped_column(ForeignKey("clients.id"))
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class Stakeholder(Base):
    """Partners, subcontractors, investors, institutional and secondary contacts."""

    __tablename__ = "stakeholders"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    relationship_type: Mapped[RelationshipType] = mapped_column(as_db_enum(RelationshipType))
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class MoodCheckin(Base):
    """Pretzel Day daily check-in.

    Attributed, not anonymous, by design: the trust model is the manager
    protecting the team's data, not the tool anonymizing it.
    """

    __tablename__ = "mood_checkins"

    id: Mapped[int] = mapped_column(primary_key=True)
    team_member_id: Mapped[int] = mapped_column(ForeignKey("team_members.id"))
    mood_level: Mapped[MoodLevel] = mapped_column(as_db_enum(MoodLevel))
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
