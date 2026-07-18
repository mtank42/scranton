"""Pretzel Day endpoints: record a check-in, read the history."""

from fastapi import APIRouter, Depends, HTTPException, Query, status

from backend.app.api.deps import get_current_user, get_mood_service, require_member
from backend.app.domain.schemas import CurrentUserOut, MoodCheckinCreate, MoodCheckinOut
from backend.app.services.mood_service import MemberNotFoundError, MoodService

router = APIRouter(prefix="/mood", tags=["mood"])


@router.post("/checkins", response_model=MoodCheckinOut, status_code=status.HTTP_201_CREATED)
def record_checkin(
    payload: MoodCheckinCreate,
    service: MoodService = Depends(get_mood_service),
    user: CurrentUserOut = Depends(require_member),
) -> MoodCheckinOut:
    """Record one 30-second mood check-in - always for YOURSELF.

    Enforced since the identity session (lot 2): a check-in is a
    declaration, so the session identity must match the declared
    member. The manager has no mood tracking (owner decision
    2026-07-14), which require_member already guarantees.
    """
    if payload.team_member_id != user.team_member_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="A check-in is always your own.",
        )
    try:
        return service.record_checkin(payload)
    except MemberNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.get("/checkins", response_model=list[MoodCheckinOut])
def list_checkins(
    member_id: int | None = Query(default=None),
    days: int = Query(default=30, ge=1, le=365),
    service: MoodService = Depends(get_mood_service),
    user: CurrentUserOut = Depends(get_current_user),
) -> list[MoodCheckinOut]:
    """List check-ins of the last days, oldest first.

    The manager reads freely (the warm layer is his surface); a member
    only ever reads their own history, whatever the query says - the
    filter is forced server-side, not trusted from the client.
    """
    if user.role != "manager":
        member_id = user.team_member_id
    return service.list_checkins(member_id=member_id, days=days)
