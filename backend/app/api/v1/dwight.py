"""Tell Dwight endpoints: capture and validation - for the WHOLE team.

The route prefix uses the character KEY ('dwight'), never the display
name: display names live in the character config map only.

Tell Dwight is the base of the product (owner, 2026-07-19): every
team member files their daily report through it and feeds the shared
memory. The emitter doctrine (day-one data model) rules every route:
the session stamps who submits (entries.submitted_by_id, None for the
manager), and only the entry's author sees, reworks and validates its
proposals - validation is the gate to the shared memory, and the gate
belongs to whoever wrote the note.
"""

from fastapi import APIRouter, Depends, HTTPException, status

from backend.app.api.deps import get_current_user, get_dwight_service
from backend.app.domain.schemas import (
    CaptureResponse,
    CurrentUserOut,
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
    NotYourEntryError,
    SegmentNotFoundError,
    SegmentNotProposedError,
)

router = APIRouter(prefix="/dwight", tags=["dwight"])


@router.post("/entries", response_model=CaptureResponse, status_code=status.HTTP_201_CREATED)
def capture_entry(
    payload: EntryCreate,
    service: DwightService = Depends(get_dwight_service),
    user: CurrentUserOut = Depends(get_current_user),
) -> CaptureResponse:
    """Submit a raw note and receive Dwight's proposed segments.

    The raw note is persisted before any processing: even a 502 here
    means the note itself is safe (status pending). The author is the
    SESSION, never the payload: a declared submitted_by_id is
    overwritten, identity is proven, not claimed.
    """
    payload.submitted_by_id = user.team_member_id
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
    user: CurrentUserOut = Depends(get_current_user),
) -> list[EntryHistoryOut]:
    """YOUR past notes, newest first (the Pam overlay history strip)."""
    return service.history(limit=limit, offset=offset, emitter_id=user.team_member_id)


@router.post("/entries/{entry_id}/reply", response_model=CaptureResponse)
def reply_to_clarification(
    entry_id: int,
    payload: EntryReply,
    service: DwightService = Depends(get_dwight_service),
    user: CurrentUserOut = Depends(get_current_user),
) -> CaptureResponse:
    """Answer Dwight's clarifying question on a pending entry.

    The dialogue continues until Dwight can propose segments (another
    clarification may come back). The answer itself is not persisted:
    only the raw note and the resulting segments count.
    """
    try:
        return service.reply(entry_id, payload.message, emitter_id=user.team_member_id)
    except NotYourEntryError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
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
    user: CurrentUserOut = Depends(get_current_user),
) -> SegmentOut:
    """Record the emitter's decision on one proposed segment.

    Validating embeds the segment into Ask Pam's memory; rejecting keeps
    it out (the row stays in SQLite as an audit trail). A plain reject
    is also the 'Forget it' exit of the rework loop. Only the entry's
    author decides (403 otherwise) - not even the manager validates
    someone else's note.
    """
    try:
        return service.validate_segment(
            segment_id, payload.status, emitter_id=user.team_member_id
        )
    except NotYourEntryError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except SegmentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.post("/segments/{segment_id}/rework", response_model=SegmentOut)
def rework_segment(
    segment_id: int,
    payload: SegmentRework,
    service: DwightService = Depends(get_dwight_service),
    user: CurrentUserOut = Depends(get_current_user),
) -> SegmentOut:
    """Reject a proposal with a comment and get a corrected replacement.

    The loop runs until the emitter validates - or bails out through a
    plain reject on the validate endpoint ('Forget it').
    """
    try:
        return service.rework(segment_id, payload.comment, emitter_id=user.team_member_id)
    except NotYourEntryError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except SegmentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except SegmentNotProposedError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except DwightProcessingError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
