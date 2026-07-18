"""Team roster, the human profile ("what they love"), and the Maire ritual.

The data ownership split is the whole point of this service: the
personal profile and the birthday belong to the TEAM MEMBER, not to the
manager and not to the company. In the POC (single user, no auth) the
manager records on the member's behalf; in V2 each member edits their
own profile directly. Nothing here is ever used to score anyone.

Maire de Scranton: on their birthday (day + month - the year does not
exist here), a member is mayor for 24 hours. The overview is computed
on read - no scheduler, no state: the POC's answer to the scheduling
seam (a real notifier can plug in later without touching this logic).
"""

import calendar
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from backend.app.domain.models import BIRTHDAY_YEAR, TeamMember, User, UserRole
from backend.app.domain.schemas import MayorOverview, MemberOut, ProfileUpdate, UpcomingBirthday
from backend.app.services.mood_service import MemberNotFoundError

# The manager reminder horizon: "the birthday is in N days" (BACKLOG:
# Pam warns one week ahead so there is time to prepare something).
REMINDER_WINDOW_DAYS = 7


def next_occurrence(birthday: date, today: date) -> date:
    """The next calendar occurrence of a birthday's day + month.

    February 29 is celebrated on February 28 in non-leap years: a
    birthday every four years would be the opposite of a ritual.
    """
    for year in (today.year, today.year + 1):
        month, day = birthday.month, birthday.day
        if month == 2 and day == 29 and not calendar.isleap(year):
            day = 28
        candidate = date(year, month, day)
        if candidate >= today:
            return candidate
    raise AssertionError("unreachable: a birthday recurs within two years")


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

    def mayor_overview(self, *, today: date | None = None) -> MayorOverview:
        """Today's Maire de Scranton and the birthdays of the next 7 days.

        today is injectable for tests; production uses the office clock
        (local date), because a birthday is a calendar day for the
        people in the room, not a UTC instant.
        """
        today = today or date.today()
        mayor = None
        upcoming: list[UpcomingBirthday] = []
        with self.session_factory() as session:
            members = list(
                session.scalars(
                    select(TeamMember).where(
                        TeamMember.is_active.is_(True), TeamMember.birthday.is_not(None)
                    )
                )
            )
            # The manager has the right to be Maire de Scranton too
            # (owner decision 2026-07-14). His birthday lives on his
            # users row (no roster row: identity apart); id 0 marks a
            # display-only entry, never a roster reference.
            managers = session.scalars(
                select(User).where(
                    User.role == UserRole.MANAGER,
                    User.is_active.is_(True),
                    User.birthday.is_not(None),
                )
            ).all()
            members.extend(
                TeamMember(
                    id=0,
                    full_name=manager.full_name or manager.email,
                    role="Manager",
                    is_active=True,
                    birthday=manager.birthday,
                )
                for manager in managers
            )
            for member in members:
                delta = (next_occurrence(member.birthday, today) - today).days
                if delta == 0:
                    mayor = MemberOut.model_validate(member)
                elif delta <= REMINDER_WINDOW_DAYS:
                    upcoming.append(
                        UpcomingBirthday(
                            member=MemberOut.model_validate(member), in_days=delta
                        )
                    )
        upcoming.sort(key=lambda item: item.in_days)
        return MayorOverview(mayor=mayor, upcoming=upcoming)
