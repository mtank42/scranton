"""Pretzel Day endpoints: record a check-in, read the history."""

from fastapi import APIRouter, Depends, HTTPException, Query, status

from backend.app.api.deps import get_mood_service
from backend.app.domain.schemas import MoodCheckinCreate, MoodCheckinOut
from backend.app.services.mood_service import MemberNotFoundError, MoodService

router = APIRouter(prefix="/mood", tags=["mood"])


@router.post("/checkins", response_model=MoodCheckinOut, status_code=status.HTTP_201_CREATED)
def record_checkin(
    payload: MoodCheckinCreate,
    service: MoodService = Depends(get_mood_service),
) -> MoodCheckinOut:
    """Record one 30-second mood check-in for a team member."""
    try:
        return service.record_checkin(payload)
    except MemberNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.get("/checkins", response_model=list[MoodCheckinOut])
def list_checkins(
    member_id: int | None = Query(default=None),
    days: int = Query(default=30, ge=1, le=365),
    service: MoodService = Depends(get_mood_service),
) -> list[MoodCheckinOut]:
    """List check-ins of the last days, oldest first, optionally per member."""
    return service.list_checkins(member_id=member_id, days=days)
