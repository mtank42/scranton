"""Team endpoints: roster and the member-owned human profile."""

from fastapi import APIRouter, Depends, HTTPException, status

from backend.app.api.deps import get_current_user, get_team_service, require_member
from backend.app.domain.schemas import CurrentUserOut, MayorOverview, MemberOut, ProfileUpdate
from backend.app.services.mood_service import MemberNotFoundError
from backend.app.services.team_service import TeamService

router = APIRouter(prefix="/team", tags=["team"])


@router.get("/mayor", response_model=MayorOverview)
def get_mayor(
    service: TeamService = Depends(get_team_service),
    user: CurrentUserOut = Depends(get_current_user),
) -> MayorOverview:
    """Today's Maire de Scranton (if any) and the upcoming birthdays.

    Computed on read: the ritual needs no scheduler. Open to any
    logged-in user: the Maire is a team ritual, both boards show it.
    """
    return service.mayor_overview()


@router.get("/members", response_model=list[MemberOut])
def list_members(
    service: TeamService = Depends(get_team_service),
    user: CurrentUserOut = Depends(get_current_user),
) -> list[MemberOut]:
    """The active roster - shaped by role (identity session, lot 2).

    The manager sees the full rows. A member sees names and roles, plus
    their OWN profile fields: personal_profile and birthday are
    member-owned data shared with the manager, never with the whole
    room.
    """
    members = service.list_members()
    if user.role == "manager":
        return members
    for member in members:
        if member.id != user.team_member_id:
            member.personal_profile = None
            member.birthday = None
    return members


@router.put("/members/{member_id}/profile", response_model=MemberOut)
def update_profile(
    member_id: int,
    payload: ProfileUpdate,
    service: TeamService = Depends(get_team_service),
    user: CurrentUserOut = Depends(require_member),
) -> MemberOut:
    """Replace the member-owned fields: personal profile and birthday.

    Self only, enforced (identity session, lot 2): the profile belongs
    to the team member. The manager recorded on their behalf only while
    the POC had no auth; that era is over.
    """
    if member_id != user.team_member_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your own profile only.",
        )
    try:
        return service.update_profile(member_id, payload)
    except MemberNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
