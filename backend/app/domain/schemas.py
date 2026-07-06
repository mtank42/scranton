"""Pydantic models: API requests/responses, ingestion edge, LLM contracts.

Three families live here:
- API schemas (EntryCreate, CaptureResponse, ...): the HTTP contract.
- RawDoc: the normalized ingestion unit.
- Dwight proposal schemas (DwightProposal, ...): the contract the LLM
  must honor. Parsing the model output through Pydantic means a malformed
  answer fails loudly at the edge instead of corrupting the database.
"""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from backend.app.domain.models import (
    DataType,
    EntityType,
    MoodLevel,
    ProcessingStatus,
    ProposedBy,
    SourceType,
    ValidationStatus,
    ViewType,
)


class HealthResponse(BaseModel):
    """Response payload for the liveness endpoint."""

    status: str


class RawDoc(BaseModel):
    """The normalized unit produced by every IngestionSource.

    'Normalize at the edge': whatever the source (manual input, Google
    Drive, a WhatsApp export), the Tell Dwight pipeline only ever sees
    this shape. Source-specific details must never leak past the adapter.
    """

    content: str
    source_type: SourceType
    # Opaque reference back to the origin (file path, Drive file id, etc.):
    # kept for traceability, never interpreted by the pipeline.
    origin_ref: str | None = None


# --- Dwight proposal: what the LLM must return ---


class ProposedTag(BaseModel):
    """One routing tag proposed by Dwight for a segment."""

    entity_type: EntityType
    entity_id: int | None = None
    view_type: ViewType | None = None
    confidence: float = Field(ge=0.0, le=1.0)


class ProposedSegment(BaseModel):
    """One segmented, reformulated, classified chunk proposed by Dwight."""

    content: str = Field(min_length=1)
    data_type: DataType
    sensitivity_level: int = Field(ge=1, le=5)
    tags: list[ProposedTag] = []


class ProfileSuggestion(BaseModel):
    """A personal-life fact Dwight spotted, proposed for a member's profile.

    Consent-preserving by design: suggestions are transient (never
    persisted as such); the manager explicitly adds them to the profile
    or dismisses them, exactly like segment validation.
    """

    team_member_id: int
    text: str = Field(min_length=1)
    birthday: date | None = None
    # Resolved server-side from the roster; the LLM never provides it.
    member_name: str | None = None


class DwightProposal(BaseModel):
    """The full LLM answer: either segments, or one clarifying question.

    Exactly one of the two branches is meaningful: a non-null clarification
    means the note was too vague and no segment was produced.
    profile_suggestions may accompany segments (V1 human profile).
    """

    clarification: str | None = None
    segments: list[ProposedSegment] = []
    profile_suggestions: list[ProfileSuggestion] = []


# --- Dwight API surface ---


class EntryCreate(BaseModel):
    """Request body for POST /api/v1/dwight/entries."""

    raw_content: str = Field(min_length=1)
    source_type: SourceType = SourceType.NOTE
    # Null means the manager submits directly (the POC case).
    submitted_by_id: int | None = None


class TagOut(BaseModel):
    """One routing tag as stored, returned for validation."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    entity_type: EntityType
    entity_id: int | None
    view_type: ViewType | None
    proposed_by: ProposedBy
    confidence: float
    validated: bool


class SegmentOut(BaseModel):
    """One stored segment with its proposed routing."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    content: str
    segment_order: int
    data_type: DataType
    sensitivity_level: int
    validation_status: ValidationStatus
    tags: list[TagOut]


class CaptureResponse(BaseModel):
    """Response for POST /api/v1/dwight/entries.

    Either clarification is set (vague note, nothing persisted beyond the
    raw entry) or segments carries Dwight's proposal awaiting validation.
    profile_suggestions are transient: adding one to a profile is an
    explicit manager action through the team endpoints.
    """

    entry_id: int
    processing_status: ProcessingStatus
    clarification: str | None = None
    segments: list[SegmentOut] = []
    profile_suggestions: list[ProfileSuggestion] = []


class SegmentValidation(BaseModel):
    """Request body for POST /api/v1/dwight/segments/{id}/validate.

    Only the two decisions are accepted: PROPOSED is not a decision, so
    it cannot be set back through the API.
    """

    status: Literal[ValidationStatus.VALIDATED, ValidationStatus.REJECTED]


class EntryReply(BaseModel):
    """Request body for POST /api/v1/dwight/entries/{id}/reply.

    The manager's answer to Dwight's clarifying question. Not persisted
    as such (owner decision, 2026-07-06: only the raw note and the
    resulting segments count); it feeds the reprocessing context.
    """

    message: str = Field(min_length=1)


class SegmentRework(BaseModel):
    """Request body for POST /api/v1/dwight/segments/{id}/rework.

    The manager's rejection comment: what Dwight got wrong or missed.
    The loop runs until validation, unless the manager bails out with
    a plain reject ('Forget it').
    """

    comment: str = Field(min_length=1)


# --- Pam API surface ---


class PamQuery(BaseModel):
    """Request body for POST /api/v1/pam/query."""

    question: str = Field(min_length=1)


class PamSource(BaseModel):
    """One memory excerpt an answer is grounded in.

    content is re-read from SQLite (the source of truth). score comes
    from the vector index (similarity, 1.0 is best); it is None when the
    excerpt was gathered exhaustively (Smart Summaries) rather than by
    semantic search.
    """

    segment_id: int
    entry_id: int
    content: str
    data_type: DataType
    sensitivity_level: int
    score: float | None = None
    created_at: datetime


class PamAnswer(BaseModel):
    """Response for POST /api/v1/pam/query: grounded answer + its sources.

    An empty sources list means the memory had nothing relevant and the
    answer says so - Pam never answers from outside the sources.
    """

    answer: str
    sources: list[PamSource] = []


# --- Pretzel Day (mood) API surface ---


class MoodCheckinCreate(BaseModel):
    """Request body for POST /api/v1/mood/checkins.

    Attributed by design (no anonymous mode): the trust model is the
    manager protecting the data, not the tool anonymizing it.
    """

    team_member_id: int
    mood_level: MoodLevel
    note: str | None = None


class MoodCheckinOut(BaseModel):
    """One recorded check-in."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    team_member_id: int
    mood_level: MoodLevel
    note: str | None
    created_at: datetime


# --- Meet Toby v0 API surface ---


class TeamTrendPoint(BaseModel):
    """One day of team mood: average palette index across check-ins.

    The average indexes moods, never people (see MOOD_INDEX in models).
    """

    day: date
    average_mood_index: float
    checkins: int


class MemberMoodPoint(BaseModel):
    """One check-in in a member's timeline."""

    at: datetime
    mood_level: MoodLevel


class TobySignal(BaseModel):
    """One weak signal, stated as a dated fact - no score, no ranking.

    The four v0 signal types were validated with the owner (M3 plan):
    declining_mood, low_mood, sensitive_warm_segment, no_recent_checkin.
    """

    type: Literal[
        "declining_mood", "low_mood", "sensitive_warm_segment", "no_recent_checkin"
    ]
    team_member_id: int
    member_name: str
    detail: str


class TobyMemberOverview(BaseModel):
    """One member's mood timeline over the window. Facts only."""

    team_member_id: int
    full_name: str
    role: str | None
    latest_mood: MoodLevel | None
    latest_checkin_at: datetime | None
    checkins: list[MemberMoodPoint]


class TobyOverview(BaseModel):
    """Response for GET /api/v1/toby/overview: the team health picture."""

    window_days: int
    generated_at: datetime
    team_trend: list[TeamTrendPoint]
    members: list[TobyMemberOverview]
    signals: list[TobySignal]


# --- Team / human profile API surface ---


class MemberOut(BaseModel):
    """One team member, personal profile included (manager-only POC view)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    role: str | None
    is_active: bool
    birthday: date | None
    personal_profile: str | None


class ProfileUpdate(BaseModel):
    """Request body for PUT /api/v1/team/members/{id}/profile.

    PUT semantics: both fields replace the stored values as given (null
    clears). The profile belongs to the team member (data ownership
    split); in the POC the manager records on their behalf, in V2 the
    member edits it directly.
    """

    personal_profile: str | None = None
    birthday: date | None = None


class UpcomingBirthday(BaseModel):
    """One birthday inside the reminder window: the Maire-to-be."""

    member: MemberOut
    in_days: int


class MayorOverview(BaseModel):
    """Response for GET /api/v1/team/mayor.

    mayor is the member whose birthday (day + month) is today: Maire de
    Scranton for 24 hours. upcoming feeds the manager reminder ('the
    birthday is in N days - want to prepare something?') with the human
    profile along for inspiration.
    """

    mayor: MemberOut | None = None
    upcoming: list[UpcomingBirthday] = []


# --- Smart Summaries API surface ---


class SummarySection(BaseModel):
    """One filled section of a living template."""

    heading: str
    content: str


class LLMSummary(BaseModel):
    """The contract the model must honor for a summary: sections only.

    Headings are dictated by the template; the model fills content and
    never invents new sections.
    """

    sections: list[SummarySection]


class SummaryTemplateInfo(BaseModel):
    """One template as advertised by the catalog."""

    id: str
    title: str
    description: str
    # What the template is about: team_member | project | client, or
    # null for team-wide templates (radar, agenda).
    target: str | None
    window_days: int | None


class TargetOption(BaseModel):
    """One pickable target (member, project or client) for the UI."""

    id: int
    name: str


class SummaryCatalog(BaseModel):
    """Response for GET /api/v1/summaries: templates + pickable targets."""

    templates: list[SummaryTemplateInfo]
    targets: dict[str, list[TargetOption]]


class SummaryResponse(BaseModel):
    """Response for GET /api/v1/summaries/{template_id}.

    A living document: computed from the validated memory at request
    time, never stored. sources carries the exhaustive excerpt list the
    sections cite as [n].
    """

    template_id: str
    title: str
    target_label: str | None
    generated_at: datetime
    window_days: int | None
    sections: list[SummarySection]
    sources: list[PamSource]


# --- Ingestion API surface ---


class IngestSummary(BaseModel):
    """Response for POST /api/v1/ingest/gdrive: what one pull produced.

    entry_ids point at the created entries; their proposed segments
    await validation in the normal Tell Dwight flow.
    """

    documents: int = 0
    entry_ids: list[int] = []
    clarifications: int = 0
    failures: int = 0
