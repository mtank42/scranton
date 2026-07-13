"""Meet Toby v0: the team health picture - trends and weak signals.

Toby aggregates and surfaces; it never scores, ranks or evaluates a
person (north star). Every signal is a dated fact the manager already
had the right to see, brought to the surface before it is too late -
the whole point is acting at week 6, not week 14.

v0 signal catalog (validated with the owner, M3 plan):
- declining_mood: the member's last three check-ins strictly worsen.
- low_mood: the member's latest check-in is stuck or danger.
- sensitive_warm_segment: validated warm segments with sensitivity >= 4
  about this member in the window.
- no_recent_checkin: the member used to check in but has not for 7 days.

No LLM in v0: plain aggregation over SQLite. A later version may add
model-written summaries on top, never model-made judgements.
"""

from collections import defaultdict
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from backend.app.domain.models import (
    MOOD_INDEX,
    DataType,
    EntityType,
    EntrySegment,
    MoodCheckin,
    MoodLevel,
    SegmentTag,
    TeamMember,
    ValidationStatus,
)
from backend.app.domain.schemas import (
    MemberMoodPoint,
    TeamTrendPoint,
    TobyMemberOverview,
    TobyOverview,
    TobySignal,
    VoicedItem,
)
from backend.app.services.mood_service import utc_cutoff

# A member is 'silent' after this many days without a check-in.
NO_CHECKIN_DAYS = 7
# Warm segments at or above this sensitivity feed a signal.
SENSITIVE_LEVEL = 4


class TobyService:
    """Build the team overview. Pure aggregation: the database is the only seam."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        """Wire the only seam this service needs: the database."""
        self.session_factory = session_factory

    def overview(self, *, days: int = 30) -> TobyOverview:
        """Assemble trends and weak signals over the last 'days'."""
        with self.session_factory() as session:
            members = session.scalars(
                select(TeamMember)
                .where(TeamMember.is_active.is_(True))
                .order_by(TeamMember.id)
            ).all()
            checkins = session.scalars(
                select(MoodCheckin)
                .where(MoodCheckin.created_at >= utc_cutoff(days))
                .order_by(MoodCheckin.created_at)
            ).all()

            by_member: dict[int, list[MoodCheckin]] = defaultdict(list)
            for checkin in checkins:
                by_member[checkin.team_member_id].append(checkin)

            warm_by_member = self._warm_segments(session, days)
            member_overviews = [
                self._member_overview(
                    member,
                    by_member.get(member.id, []),
                    warm_by_member.get(member.id, []),
                )
                for member in members
            ]
            signals = self._collect_signals(session, members, by_member, days)

        return TobyOverview(
            window_days=days,
            generated_at=datetime.now(timezone.utc),
            team_trend=self._team_trend(checkins),
            members=member_overviews,
            signals=signals,
        )

    # --- building blocks ---

    @staticmethod
    def _warm_segments(session: Session, days: int) -> dict[int, list[EntrySegment]]:
        """Validated warm observations per member, one query for the team.

        Only VALIDATED enters (the single gate); deduplicated per member
        because a segment can carry several tags to the same person.
        """
        rows = session.execute(
            select(SegmentTag.entity_id, EntrySegment)
            .join(EntrySegment, SegmentTag.segment_id == EntrySegment.id)
            .where(
                SegmentTag.entity_type == EntityType.TEAM_MEMBER,
                EntrySegment.data_type == DataType.WARM,
                EntrySegment.validation_status == ValidationStatus.VALIDATED,
                EntrySegment.created_at >= utc_cutoff(days),
            )
        ).all()
        by_member: dict[int, list[EntrySegment]] = defaultdict(list)
        seen: set[tuple[int, int]] = set()
        for member_id, segment in rows:
            if member_id is None or (member_id, segment.id) in seen:
                continue
            seen.add((member_id, segment.id))
            by_member[member_id].append(segment)
        return by_member

    @staticmethod
    def _member_overview(
        member: TeamMember,
        checkins: list[MoodCheckin],
        warm_segments: list[EntrySegment],
    ) -> TobyMemberOverview:
        """One member's timeline: raw dated facts, chronological.

        voiced carries what the person (or the manager's validated
        observation) actually SAID, newest first - the drill-down the
        recadrage asked for, instead of dots with a thousand causes.
        """
        latest = checkins[-1] if checkins else None
        voiced = [
            VoicedItem(at=checkin.created_at, text=checkin.note, kind="checkin_note")
            for checkin in checkins
            if checkin.note
        ] + [
            VoicedItem(
                at=segment.created_at,
                text=segment.content,
                kind="warm_segment",
                sensitivity_level=segment.sensitivity_level,
            )
            for segment in warm_segments
        ]
        voiced.sort(key=lambda item: item.at, reverse=True)
        return TobyMemberOverview(
            team_member_id=member.id,
            full_name=member.full_name,
            role=member.role,
            latest_mood=latest.mood_level if latest else None,
            latest_checkin_at=latest.created_at if latest else None,
            checkins=[
                MemberMoodPoint(
                    at=checkin.created_at,
                    mood_level=checkin.mood_level,
                    note=checkin.note,
                )
                for checkin in checkins
            ],
            voiced=voiced,
        )

    @staticmethod
    def _team_trend(checkins: list[MoodCheckin]) -> list[TeamTrendPoint]:
        """Average palette index per day, across all members.

        Averaging the mood index is averaging moods over a day, never
        rating a person: individual timelines stay raw levels.
        """
        by_day: dict = defaultdict(list)
        for checkin in checkins:
            by_day[checkin.created_at.date()].append(MOOD_INDEX[checkin.mood_level])
        return [
            TeamTrendPoint(
                day=day,
                average_mood_index=round(sum(indexes) / len(indexes), 2),
                checkins=len(indexes),
            )
            for day, indexes in sorted(by_day.items())
        ]

    def _collect_signals(
        self,
        session: Session,
        members: list[TeamMember],
        by_member: dict[int, list[MoodCheckin]],
        days: int,
    ) -> list[TobySignal]:
        """Run the four v0 detectors for every active member."""
        signals: list[TobySignal] = []
        for member in members:
            checkins = by_member.get(member.id, [])
            signals.extend(self._mood_signals(member, checkins))
            silent = self._no_recent_checkin_signal(session, member, checkins)
            if silent:
                signals.append(silent)
            sensitive = self._sensitive_segment_signal(session, member, days)
            if sensitive:
                signals.append(sensitive)
        return signals

    @staticmethod
    def _mood_signals(
        member: TeamMember, checkins: list[MoodCheckin]
    ) -> list[TobySignal]:
        """declining_mood and low_mood, from the member's window timeline."""
        signals = []
        if len(checkins) >= 3:
            last_three = [MOOD_INDEX[c.mood_level] for c in checkins[-3:]]
            if last_three[0] > last_three[1] > last_three[2]:
                path = " -> ".join(c.mood_level.value for c in checkins[-3:])
                signals.append(
                    TobySignal(
                        type="declining_mood",
                        team_member_id=member.id,
                        member_name=member.full_name,
                        detail=f"Last three check-ins worsen: {path}.",
                    )
                )
        if checkins and checkins[-1].mood_level in (MoodLevel.STUCK, MoodLevel.DANGER):
            latest = checkins[-1]
            signals.append(
                TobySignal(
                    type="low_mood",
                    team_member_id=member.id,
                    member_name=member.full_name,
                    detail=(
                        f"Latest check-in is {latest.mood_level.value} "
                        f"({latest.created_at:%Y-%m-%d})."
                    ),
                )
            )
        return signals

    @staticmethod
    def _no_recent_checkin_signal(
        session: Session, member: TeamMember, window_checkins: list[MoodCheckin]
    ) -> TobySignal | None:
        """Silence detector: used to check in, but not in the last 7 days.

        Members who never checked in at all are excluded: a fresh roster
        must not open with a wall of alarms.
        """
        recent = [
            c for c in window_checkins if c.created_at >= utc_cutoff(NO_CHECKIN_DAYS)
        ]
        if recent:
            return None
        ever = session.scalar(
            select(func.count())
            .select_from(MoodCheckin)
            .where(MoodCheckin.team_member_id == member.id)
        )
        if not ever:
            return None
        return TobySignal(
            type="no_recent_checkin",
            team_member_id=member.id,
            member_name=member.full_name,
            detail=f"No check-in for more than {NO_CHECKIN_DAYS} days.",
        )

    @staticmethod
    def _sensitive_segment_signal(
        session: Session, member: TeamMember, days: int
    ) -> TobySignal | None:
        """Validated warm segments with high sensitivity about this member."""
        count = session.scalar(
            select(func.count(func.distinct(EntrySegment.id)))
            .select_from(EntrySegment)
            .join(SegmentTag, SegmentTag.segment_id == EntrySegment.id)
            .where(
                SegmentTag.entity_type == EntityType.TEAM_MEMBER,
                SegmentTag.entity_id == member.id,
                EntrySegment.data_type == DataType.WARM,
                EntrySegment.sensitivity_level >= SENSITIVE_LEVEL,
                EntrySegment.validation_status == ValidationStatus.VALIDATED,
                EntrySegment.created_at >= utc_cutoff(days),
            )
        )
        if not count:
            return None
        plural = "s" if count > 1 else ""
        return TobySignal(
            type="sensitive_warm_segment",
            team_member_id=member.id,
            member_name=member.full_name,
            detail=(
                f"{count} sensitive observation{plural} "
                f"(level >= {SENSITIVE_LEVEL}) recorded in the window."
            ),
        )
