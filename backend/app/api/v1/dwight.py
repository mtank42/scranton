"""Tell Dwight endpoints: capture and validation.

The route prefix uses the character KEY ('dwight'), never the display
name: display names live in the character config map only.
"""

from fastapi import APIRouter, Depends, HTTPException, status

from backend.app.api.deps import get_dwight_service
from backend.app.domain.schemas import (
    CaptureResponse,
    EntryCreate,
    EntryHistoryOut,
    EntryReply,
    SegmentOut,
    SegmentRework,
    SegmentValidation,
)
from backend.app.services.dwight_service import (
    DwightProcessingError,
    DwightService,
    EntryNotFoundError,
    EntryNotPendingError,
    SegmentNotFoundError,
    SegmentNotProposedError,
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


@router.get("/entries/recent", response_model=list[EntryHistoryOut])
def recent_entries(
    limit: int = 5,
    offset: int = 0,
    service: DwightService = Depends(get_dwight_service),
) -> list[EntryHistoryOut]:
    """Past notes, newest first: the Pam overlay history strip."""
    return service.history(limit=limit, offset=offset)


@router.post("/entries/{entry_id}/reply", response_model=CaptureResponse)
def reply_to_clarification(
    entry_id: int,
    payload: EntryReply,
    service: DwightService = Depends(get_dwight_service),
) -> CaptureResponse:
    """Answer Dwight's clarifying question on a pending entry.

    The dialogue continues until Dwight can propose segments (another
    clarification may come back). The answer itself is not persisted:
    only the raw note and the resulting segments count.
    """
    try:
        return service.reply(entry_id, payload.message)
    except EntryNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except EntryNotPendingError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except DwightProcessingError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))


@router.post("/segments/{segment_id}/validate", response_model=SegmentOut)
def validate_segment(
    segment_id: int,
    payload: SegmentValidation,
    service: DwightService = Depends(get_dwight_service),
) -> SegmentOut:
    """Record the manager's decision on one proposed segment.

    Validating embeds the segment into Ask Pam's memory; rejecting keeps
    it out (the row stays in SQLite as an audit trail). A plain reject
    is also the 'Forget it' exit of the rework loop.
    """
    try:
        return service.validate_segment(segment_id, payload.status)
    except SegmentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.post("/segments/{segment_id}/rework", response_model=SegmentOut)
def rework_segment(
    segment_id: int,
    payload: SegmentRework,
    service: DwightService = Depends(get_dwight_service),
) -> SegmentOut:
    """Reject a proposal with a comment and get a corrected replacement.

    The loop runs until the manager validates - or bails out through a
    plain reject on the validate endpoint ('Forget it').
    """
    try:
        return service.rework(segment_id, payload.comment)
    except SegmentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except SegmentNotProposedError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except DwightProcessingError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
