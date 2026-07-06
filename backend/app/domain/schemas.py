"""Pydantic models: API requests/responses, ingestion edge, LLM contracts.

Three families live here:
- API schemas (EntryCreate, CaptureResponse, ...): the HTTP contract.
- RawDoc: the normalized ingestion unit.
- Dwight proposal schemas (DwightProposal, ...): the contract the LLM
  must honor. Parsing the model output through Pydantic means a malformed
  answer fails loudly at the edge instead of corrupting the database.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from backend.app.domain.models import (
    DataType,
    EntityType,
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


class DwightProposal(BaseModel):
    """The full LLM answer: either segments, or one clarifying question.

    Exactly one of the two branches is meaningful: a non-null clarification
    means the note was too vague and no segment was produced.
    """

    clarification: str | None = None
    segments: list[ProposedSegment] = []


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
    """

    entry_id: int
    processing_status: ProcessingStatus
    clarification: str | None = None
    segments: list[SegmentOut] = []


class SegmentValidation(BaseModel):
    """Request body for POST /api/v1/dwight/segments/{id}/validate.

    Only the two decisions are accepted: PROPOSED is not a decision, so
    it cannot be set back through the API.
    """

    status: Literal[ValidationStatus.VALIDATED, ValidationStatus.REJECTED]
