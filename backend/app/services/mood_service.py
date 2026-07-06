"""Pretzel Day: record and list mood check-ins.

The 30-second ritual: one member, one of six mood levels, an optional
note. Check-ins are attributed (not anonymous) by design - the manager
protects the team's data, the tool does not hide the team from the
manager. No LLM anywhere in this pipeline.
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from backend.app.domain.models import MoodCheckin, TeamMember
from backend.app.domain.schemas import MoodCheckinCreate, MoodCheckinOut


class MemberNotFoundError(Exception):
    """The referenced team member does not exist."""


def utc_cutoff(days: int) -> datetime:
    """Naive-UTC datetime 'days' ago, matching how SQLite stores our dates.

    SQLAlchemy's plain DateTime column stores naive values in SQLite, so
    comparisons must use naive UTC on both sides.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days)


class MoodService:
    """Record check-ins and expose their history."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        """Wire the only seam this service needs: the database."""
        self.session_factory = session_factory

    def record_checkin(self, payload: MoodCheckinCreate) -> MoodCheckinOut:
        """Persist one check-in for an existing team member."""
        with self.session_factory() as session:
            member = session.get(TeamMember, payload.team_member_id)
            if member is None:
                raise MemberNotFoundError(
                    f"No team member with id {payload.team_member_id}."
                )
            checkin = MoodCheckin(
                team_member_id=payload.team_member_id,
                mood_level=payload.mood_level,
                note=payload.note,
            )
            session.add(checkin)
            session.commit()
            return MoodCheckinOut.model_validate(checkin)

    def list_checkins(
        self, *, member_id: int | None = None, days: int = 30
    ) -> list[MoodCheckinOut]:
        """Return check-ins of the last 'days', oldest first.

        Oldest first because every consumer (trend charts, Toby) reads
        time left to right.
        """
        query = (
            select(MoodCheckin)
            .where(MoodCheckin.created_at >= utc_cutoff(days))
            .order_by(MoodCheckin.created_at)
        )
        if member_id is not None:
            query = query.where(MoodCheckin.team_member_id == member_id)
        with self.session_factory() as session:
            return [
                MoodCheckinOut.model_validate(checkin)
                for checkin in session.scalars(query).all()
            ]
