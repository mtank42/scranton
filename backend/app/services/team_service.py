"""Team roster and the human profile ("what they love").

The data ownership split is the whole point of this service: the
personal profile and the birthday belong to the TEAM MEMBER, not to the
manager and not to the company. In the POC (single user, no auth) the
manager records on the member's behalf; in V2 each member edits their
own profile directly. Nothing here is ever used to score anyone.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from backend.app.domain.models import BIRTHDAY_YEAR, TeamMember
from backend.app.domain.schemas import MemberOut, ProfileUpdate
from backend.app.services.mood_service import MemberNotFoundError


class TeamService:
    """Read the roster, update the member-owned profile fields."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        """Wire the only seam this service needs: the database."""
        self.session_factory = session_factory

    def list_members(self) -> list[MemberOut]:
        """Return the active roster, profiles included (manager-only POC)."""
        with self.session_factory() as session:
            members = session.scalars(
                select(TeamMember)
                .where(TeamMember.is_active.is_(True))
                .order_by(TeamMember.full_name)
            ).all()
            return [MemberOut.model_validate(member) for member in members]

    def update_profile(self, member_id: int, payload: ProfileUpdate) -> MemberOut:
        """Replace the member-owned fields (PUT semantics: null clears).

        Only personal_profile and birthday are touchable here: the
        professional fields (name, role, is_active) belong to the
        manager side and have no reason to change in this flow.
        """
        with self.session_factory() as session:
            member = session.get(TeamMember, member_id)
            if member is None:
                raise MemberNotFoundError(f"No team member with id {member_id}.")
            member.personal_profile = payload.personal_profile
            # A birthday is a day, not an age: whatever year arrives, it is
            # erased (normalized to BIRTHDAY_YEAR) and never shown again.
            member.birthday = (
                payload.birthday.replace(year=BIRTHDAY_YEAR) if payload.birthday else None
            )
            session.commit()
            return MemberOut.model_validate(member)
