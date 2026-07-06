"""Tell Dwight endpoints: capture and validation.

The route prefix uses the character KEY ('dwight'), never the display
name: display names live in the character config map only.
"""

from fastapi import APIRouter, Depends, HTTPException, status

from backend.app.api.deps import get_dwight_service
from backend.app.domain.schemas import CaptureResponse, EntryCreate, SegmentOut, SegmentValidation
from backend.app.services.dwight_service import (
    DwightProcessingError,
    DwightService,
    SegmentNotFoundError,
)

router = APIRouter(prefix="/dwight", tags=["dwight"])


@router.post("/entries", response_model=CaptureResponse, status_code=status.HTTP_201_CREATED)
def capture_entry(
    payload: EntryCreate,
    service: DwightService = Depends(get_dwight_service),
) -> CaptureResponse:
    """Submit a raw note and receive Dwight's proposed segments.

    The raw note is persisted before any processing: even a 502 here
    means the note itself is safe (status pending).
    """
    try:
        return service.capture(payload)
    except DwightProcessingError as exc:
        # 502: the upstream model failed us, not the client.
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))


@router.post("/segments/{segment_id}/validate", response_model=SegmentOut)
def validate_segment(
    segment_id: int,
    payload: SegmentValidation,
    service: DwightService = Depends(get_dwight_service),
) -> SegmentOut:
    """Record the manager's decision on one proposed segment.

    Validating embeds the segment into Ask Pam's memory; rejecting keeps
    it out (the row stays in SQLite as an audit trail).
    """
    try:
        return service.validate_segment(segment_id, payload.status)
    except SegmentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
