"""Team endpoints: roster and the member-owned human profile."""

from fastapi import APIRouter, Depends, HTTPException, status

from backend.app.api.deps import get_team_service
from backend.app.domain.schemas import MemberOut, ProfileUpdate
from backend.app.services.mood_service import MemberNotFoundError
from backend.app.services.team_service import TeamService

router = APIRouter(prefix="/team", tags=["team"])


@router.get("/members", response_model=list[MemberOut])
def list_members(service: TeamService = Depends(get_team_service)) -> list[MemberOut]:
    """The active roster with profiles (manager-only in the POC)."""
    return service.list_members()


@router.put("/members/{member_id}/profile", response_model=MemberOut)
def update_profile(
    member_id: int,
    payload: ProfileUpdate,
    service: TeamService = Depends(get_team_service),
) -> MemberOut:
    """Replace the member-owned fields: personal profile and birthday.

    Owned by the team member (data ownership split); the manager records
    on their behalf only because the POC has no auth yet.
    """
    try:
        return service.update_profile(member_id, payload)
    except MemberNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
