"""Pydantic models shared across the API surface and the ingestion edge."""

from pydantic import BaseModel

from backend.app.domain.models import SourceType


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
