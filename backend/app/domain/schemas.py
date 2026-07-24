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
    DocumentProposedBy,
    DocumentStatus,
    EntityType,
    HandoverStatus,
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
    privacy_note is Dwight saying out loud that personal-life info was
    left out (owner, QA 2026-07-14: the silent drop felt broken) - an
    acknowledgment, never a suggestion to store anything.
    """

    clarification: str | None = None
    segments: list[ProposedSegment] = []
    profile_suggestions: list[ProfileSuggestion] = []
    privacy_note: str | None = None


# --- Dwight API surface ---


class EntryCreate(BaseModel):
    """Request body for POST /api/v1/dwight/entries."""

    raw_content: str = Field(min_length=1)
    source_type: SourceType = SourceType.NOTE
    # The author. OVERWRITTEN from the session by the route (identity
    # is proven, never claimed); None means the manager.
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
    # Dwight's spoken acknowledgment that personal-life info stayed out.
    privacy_note: str | None = None


class EntryHistoryOut(BaseModel):
    """One past note in the Pam overlay history strip.

    The raw note is what the manager remembers writing, so it is the
    anchor; the segment counters say what became of it without loading
    the segments themselves (the strip is a glance, not an audit view).
    """

    id: int
    raw_content: str
    source_type: SourceType
    created_at: datetime
    segments_total: int
    segments_validated: int


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
    """One excerpt an answer is grounded in - from either memory.

    content is re-read from SQLite (the source of truth). score comes
    from the vector index (similarity, 1.0 is best); it is None when the
    excerpt was gathered exhaustively (Smart Summaries) rather than by
    semantic search. ref is the excerpt number shared by the prompt and
    the [n] citations, so a filtered source list keeps honest numbering;
    None on paths that never cite (template gathering).

    kind badges the two memories (owner arbitration, 2026-07-15):
    'memory' is a validated team segment (segment_id/entry_id set),
    'document' is a corpus chunk (document_id/title set, link when the
    source has one - the clickable way back to the original).
    """

    ref: int | None = None
    kind: Literal["memory", "document"] = "memory"
    segment_id: int | None = None
    entry_id: int | None = None
    document_id: int | None = None
    title: str | None = None
    link: str | None = None
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
    # Recadrage 2026-07-12: summaries are Pam RESPONSE TEMPLATES. When
    # the question asks for the broad picture of one known entity, Pam
    # serves the matching template here. None on the plain Q&A path.
    # (Forward reference: SummaryResponse is defined below; the model is
    # rebuilt right after it.)
    summary: "SummaryResponse | None" = None


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
    # The member's own words, when they left any (recadrage 2026-07-12:
    # Toby surfaces what people VERBALIZED, not just colored dots).
    note: str | None = None


class VoicedItem(BaseModel):
    """One thing a member actually said, dated and quoted.

    Either their own check-in note or a validated warm observation
    about them. Material for a conversation - never a verdict.
    """

    at: datetime
    text: str
    kind: Literal["checkin_note", "warm_segment"]
    sensitivity_level: int | None = None


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
    # What they verbalized in the window, newest first: check-in notes
    # and validated warm observations (recadrage 2026-07-12 drill-down).
    voiced: list[VoicedItem] = []


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
    # The target as ids, not just a label: what the save gesture needs
    # to persist an edited document (editing session, 2026-07-16).
    target_type: str | None = None
    target_id: int | None = None
    generated_at: datetime
    window_days: int | None
    sections: list[SummarySection]
    sources: list[PamSource]


# PamAnswer.summary forward-references SummaryResponse (defined above):
# resolve it now that both classes exist.
PamAnswer.model_rebuild()


# --- Transfer to Philly (handover) API surface ---

# The portable contract identity. Case 2 (V2) makes two Scranton
# instances exchange this document, so its shape is a promise: bump the
# version ONLY with a migration note in docs/transfer_to_philly.md.
HANDOVER_SCHEMA = "scranton.handover.member"
HANDOVER_SCHEMA_VERSION = 1


class HandoverItem(BaseModel):
    """One VERBATIM validated segment inside a handover dossier.

    Verbatim on purpose: a GDPR consent artifact carries the exact
    validated text, never a model paraphrase.
    """

    segment_id: int
    content: str
    data_type: DataType
    sensitivity_level: int
    created_at: datetime
    # Human-readable routing labels (entity names, view names), resolved
    # at generation time: context for the receiving manager.
    topics: list[str] = []


class HandoverDossier(BaseModel):
    """The portable handover document (Transfer to Philly, case 1).

    Cold data is transmissible a priori; warm data is the manager's
    explicit selection, sensitivity-sorted for review. The member-owned
    human profile and the mood history are NEVER part of a handover:
    they belong to the member, who discloses to whom they choose.
    """

    schema_id: str = HANDOVER_SCHEMA
    schema_version: int = HANDOVER_SCHEMA_VERSION
    generated_at: datetime
    member_id: int
    member_name: str
    member_role: str | None
    cold: list[HandoverItem]
    warm: list[HandoverItem]
    # Transparency for the receiving side: how many warm observations
    # the outgoing manager chose NOT to transmit. The count travels,
    # the content never does.
    excluded_warm_count: int = 0


class HandoverValidationCreate(BaseModel):
    """Request body for POST /api/v1/handover/{member_id}/validations.

    The default is an empty selection on purpose: nothing warm is
    disclosed unless the manager explicitly selects it.
    """

    disclosed_warm_ids: list[int] = []


class HandoverSelectionUpdate(BaseModel):
    """Request body for PUT /api/v1/handover/validations/{id}/selection."""

    disclosed_warm_ids: list[int]


class HandoverSignatures(BaseModel):
    """Request body for POST /api/v1/handover/validations/{id}/sign.

    Typed name + server timestamp is the POC signature level (owner
    decision, 2026-07-08); a content hash per signature is the case 2
    upgrade. Both names arrive together because in the POC the two
    parties sign side by side, on the manager's screen.
    """

    manager_name: str = Field(min_length=1, max_length=120)
    member_name: str = Field(min_length=1, max_length=120)


class HandoverValidationOut(BaseModel):
    """One handover consent record: the audit trail of who agreed to what.

    disclosed_warm_ids is the selection under consent; fiche_sha256 is
    the integrity anchor of the signed artifact (set at signature time).
    """

    id: int
    team_member_id: int
    status: HandoverStatus
    disclosed_warm_ids: list[int]
    fiche_sha256: str | None
    manager_signature_name: str | None
    manager_signed_at: datetime | None
    member_signature_name: str | None
    member_signed_at: datetime | None
    created_at: datetime
    reviewed_at: datetime | None
    validated_at: datetime | None
    sent_at: datetime | None


# --- Darryl (documentary corpus) API surface ---


class DarrylProposedTag(BaseModel):
    """One routing tag proposed by Darryl's LLM fallback.

    client / project only: documents feed the client and project files
    (owner arbitration, 2026-07-15); people never route through the
    corpus. entity_id is mandatory - there are no view tags here.
    """

    entity_type: Literal[EntityType.CLIENT, EntityType.PROJECT]
    entity_id: int
    confidence: float = Field(ge=0.0, le=1.0)


class DarrylRouting(BaseModel):
    """The routing contract the fallback LLM must honor.

    An empty tag list is a VALID answer: it sends the document to the
    unclassified bin, which is Darryl doing his job (never a bet), not
    a failure.
    """

    tags: list[DarrylProposedTag] = []


class DocumentTagOut(BaseModel):
    """One document routing tag as stored."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    entity_type: EntityType
    entity_id: int
    proposed_by: DocumentProposedBy
    confidence: float


class DocumentOut(BaseModel):
    """One corpus document, routing included (the audit surface unit)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    mime_type: str
    web_view_link: str | None
    folder_path: str
    modified_at: datetime | None
    status: DocumentStatus
    family_key: str
    is_latest: bool
    ingested_at: datetime
    tags: list[DocumentTagOut]


class DocumentDetail(DocumentOut):
    """One document with its extracted text: the preview surface.

    content is re-read from SQLite (document_chunks, the source of
    truth) - the preview shows exactly what Pam reasons over. None for
    catalog-only formats (spreadsheets) and failed extractions: those
    are known by name and link only, the Drive link is the way in.
    """

    content: str | None = None


class DarrylSyncReport(BaseModel):
    """Response for POST /api/v1/darryl/sync: what one pass did.

    unclassified is the bin size AFTER the sync (not the delta): what
    the manager may want to file, surfaced in the Pam overlay.
    """

    seen: int = 0
    added: int = 0
    updated: int = 0
    removed: int = 0
    unclassified: int = 0


class DocumentClassify(BaseModel):
    """Request body for POST /api/v1/darryl/documents/{id}/classify.

    The manager filing (or re-filing) one document: a decision, so it
    replaces Darryl's routing rather than piling on top of it.
    """

    entity_type: Literal[EntityType.CLIENT, EntityType.PROJECT]
    entity_id: int


# --- Edited documents API surface (document-editing session, 2026-07-16) ---


class EditedDocumentCreate(BaseModel):
    """Request body for POST /api/v1/documents: persist a generation.

    The first save is the human gesture that turns a living template
    output into the manager's own document.
    """

    title: str = Field(min_length=1, max_length=300)
    template_key: str = Field(min_length=1, max_length=50)
    target_entity_type: EntityType | None = None
    target_entity_id: int | None = None
    content_md: str = Field(min_length=1)
    generated_at: datetime


class EditedDocumentUpdate(BaseModel):
    """Request body for POST /api/v1/documents/{id}/save: a re-edit."""

    content_md: str = Field(min_length=1)


class EditedDocumentOut(BaseModel):
    """One persisted document; news_count is the delta badge."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    template_key: str
    target_entity_type: EntityType | None
    target_entity_id: int | None
    content_md: str
    generated_at: datetime
    created_at: datetime
    updated_at: datetime
    memory_reviewed_at: datetime
    # Validated segments about the target since memory_reviewed_at.
    news_count: int = 0


class DocumentDelta(BaseModel):
    """What's new for one document: the proposals to triage."""

    document_id: int
    segments: list[PamSource]


class DocumentReviseRequest(BaseModel):
    """Request body for POST /api/v1/documents/{id}/revise.

    The context travels with the instruction (owner decision,
    2026-07-14): the service hands Dwight the current document, the
    instruction, and the selected news segments - never a bare order.

    content_md carries the editor's canvas when it differs from the
    saved state (C3, 2026-07-17: edits apply to the canvas and persist
    only at Save) - None means revise the saved text.
    """

    instruction: str = Field(min_length=1)
    include_segment_ids: list[int] = []
    content_md: str | None = None


class DraftReviseRequest(BaseModel):
    """Request body for POST /api/v1/documents/revise: a draft revision.

    C3 (2026-07-17): 'Edit' opens the editor WITHOUT persisting - the
    document is born at the first Save. Until then Dwight revises the
    draft content directly; no id, no delta (nothing saved to move
    against).
    """

    content_md: str = Field(min_length=1)
    instruction: str = Field(min_length=1)


class DiffRequest(BaseModel):
    """Request body for POST /api/v1/documents/diff: a manual edit.

    The diff stays COMPUTED wherever the edit came from (owner, C3):
    the frontend never diffs by itself, it asks the same difflib that
    highlights Dwight's revisions.
    """

    before: str
    after: str


class DiffSpan(BaseModel):
    """One span of the review diff: how the proposal differs.

    Computed with difflib, never self-reported by the model: the
    highlighting is guaranteed by the computation (owner request,
    2026-07-16 - see at a glance what Dwight changed).
    """

    op: Literal["equal", "insert", "delete"]
    text: str


class DocumentRevision(BaseModel):
    """Response for the revise endpoints: nothing persisted.

    The revision applies to the caller's canvas (C3: apply + Undo, the
    standard editor model); persisting stays a separate explicit Save.
    document_id is None for a draft revision - no document exists yet.
    """

    document_id: int | None = None
    content_md: str
    diff: list[DiffSpan]


class DocumentDiff(BaseModel):
    """Response for POST /api/v1/documents/diff: the computed spans."""

    diff: list[DiffSpan]


class DwightRevision(BaseModel):
    """The contract the model must honor for a document revision."""

    content_md: str


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


# --- Auth API surface (identity session, 2026-07-18) ---


class AuthStatus(BaseModel):
    """Response for GET /api/v1/auth/status: what the landing shows.

    initialized False means no manager account exists yet: the entry
    screen is the first-run setup, not the login form.
    """

    initialized: bool


class SetupIn(BaseModel):
    """Request body for POST /api/v1/auth/setup (first run only).

    The email doubles as the login (owner arbitration 2026-07-18: mail
    only). A light shape check is enough here: the email is a login
    identifier we store, not an address we deliver to - full RFC
    validation would add a dependency for no protection.
    """

    email: str = Field(pattern=r".+@.+\..+")
    # 8 characters is the floor, not a policy statement: length is the
    # one constraint that measurably helps, composition rules do not.
    password: str = Field(min_length=8)
    full_name: str = Field(min_length=1)
    birthday: date | None = None


class LoginIn(BaseModel):
    """Request body for POST /api/v1/auth/login."""

    email: str
    password: str


class ChangePasswordIn(BaseModel):
    """Request body for POST /api/v1/auth/change-password.

    The current password is required even with a valid session cookie:
    an unattended machine must not be enough to take over an account.
    """

    current_password: str
    new_password: str = Field(min_length=8)


class CurrentUserOut(BaseModel):
    """The logged-in identity, as the frontend sees it.

    role drives which views exist; must_change_password True forces the
    password screen before anything else (admin-created accounts).
    """

    id: int
    email: str
    role: str
    full_name: str | None
    team_member_id: int | None
    must_change_password: bool


# --- Admin API surface (identity session, lot 3) ---


class AdminMemberOut(BaseModel):
    """One roster row as the Admin view sees it: account included.

    has_account False marks a roster row that predates the identity
    session; giving it an email (update) creates its account.
    """

    member_id: int
    full_name: str
    role: str | None
    email: str | None
    is_active: bool
    has_account: bool


class AdminAccountCreated(BaseModel):
    """A created (or reset) account, with its provisional password.

    The password's ONLY exposure: never stored in clear, never shown
    again - the admin reads it to the member, first login replaces it.
    """

    member: AdminMemberOut
    provisional_password: str


class AdminMemberCreate(BaseModel):
    """Request body for POST /api/v1/admin/members."""

    full_name: str = Field(min_length=1)
    role: str | None = None
    email: str = Field(pattern=r".+@.+\..+")


class AdminMemberUpdate(BaseModel):
    """Request body for PUT /api/v1/admin/members/{id}: the
    professional fields only (member-owned data has its own flow)."""

    full_name: str = Field(min_length=1)
    role: str | None = None
    email: str = Field(pattern=r".+@.+\..+")
