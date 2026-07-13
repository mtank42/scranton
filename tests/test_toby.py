"""Meet Toby v0: trends and the four weak-signal detectors."""

from datetime import datetime, timedelta, timezone

from backend.app.domain.models import (
    DataType,
    EntityType,
    Entry,
    EntrySegment,
    MoodCheckin,
    MoodLevel,
    ProposedBy,
    SegmentTag,
    SourceType,
    TeamMember,
    ValidationStatus,
)
from backend.app.services.toby_service import TobyService


def utc_naive(days_ago: int) -> datetime:
    """A naive-UTC timestamp 'days_ago' days in the past (SQLite format)."""
    return datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days_ago)


def seed_member(session_factory, name: str) -> int:
    """Insert one active team member and return its id."""
    with session_factory() as session:
        member = TeamMember(full_name=name)
        session.add(member)
        session.commit()
        return member.id


def add_checkins(session_factory, member_id: int, moods: list[tuple[int, MoodLevel]]):
    """Insert (days_ago, mood) check-ins for a member."""
    with session_factory() as session:
        for days_ago, mood in moods:
            session.add(
                MoodCheckin(
                    team_member_id=member_id,
                    mood_level=mood,
                    created_at=utc_naive(days_ago),
                )
            )
        session.commit()


def signals_for(overview, member_id: int) -> set[str]:
    """The signal types raised for one member."""
    return {s.type for s in overview.signals if s.team_member_id == member_id}


def test_healthy_member_raises_no_signal(session_factory):
    """Steady good moods: timeline present, zero alarms."""
    member_id = seed_member(session_factory, "Jim")
    add_checkins(
        session_factory,
        member_id,
        [(3, MoodLevel.FLOW), (2, MoodLevel.CTRL), (1, MoodLevel.FLOW)],
    )

    overview = TobyService(session_factory).overview()

    assert signals_for(overview, member_id) == set()
    member = next(m for m in overview.members if m.team_member_id == member_id)
    assert member.latest_mood == MoodLevel.FLOW
    assert len(member.checkins) == 3


def test_declining_mood_is_detected(session_factory):
    """The Sonia trajectory: three strictly worsening check-ins."""
    member_id = seed_member(session_factory, "Sonia")
    add_checkins(
        session_factory,
        member_id,
        [(3, MoodLevel.CTRL), (2, MoodLevel.PRESS), (1, MoodLevel.STUCK)],
    )

    overview = TobyService(session_factory).overview()

    assert signals_for(overview, member_id) == {"declining_mood", "low_mood"}
    declining = next(s for s in overview.signals if s.type == "declining_mood")
    assert "ctrl -> press -> stuck" in declining.detail


def test_low_mood_alone_without_decline(session_factory):
    """A single danger check-in flags low_mood but not declining_mood."""
    member_id = seed_member(session_factory, "Stanley")
    add_checkins(session_factory, member_id, [(1, MoodLevel.DANGER)])

    overview = TobyService(session_factory).overview()

    assert signals_for(overview, member_id) == {"low_mood"}


def test_silence_is_flagged_only_for_past_checkin_users(session_factory):
    """No check-in for 7+ days flags members who used to check in.

    A member who never checked in stays silent: a fresh roster must not
    open with a wall of alarms.
    """
    quiet_id = seed_member(session_factory, "Kevin")
    add_checkins(session_factory, quiet_id, [(12, MoodLevel.FLOW)])
    new_id = seed_member(session_factory, "Ryan")

    overview = TobyService(session_factory).overview()

    assert signals_for(overview, quiet_id) == {"no_recent_checkin"}
    assert signals_for(overview, new_id) == set()


def test_sensitive_warm_segments_feed_a_signal(session_factory):
    """Validated warm segments with sensitivity >= 4 surface, others do not."""
    member_id = seed_member(session_factory, "Oscar")
    with session_factory() as session:
        entry = Entry(raw_content="raw", source_type=SourceType.NOTE)
        session.add(entry)
        session.flush()
        flagged = EntrySegment(
            entry_id=entry.id,
            content="Mentioned exhaustion and looking elsewhere.",
            segment_order=0,
            data_type=DataType.WARM,
            sensitivity_level=5,
            validation_status=ValidationStatus.VALIDATED,
        )
        ignored_proposed = EntrySegment(
            entry_id=entry.id,
            content="Another sensitive note, not validated yet.",
            segment_order=1,
            data_type=DataType.WARM,
            sensitivity_level=5,
        )
        ignored_mild = EntrySegment(
            entry_id=entry.id,
            content="Prefers morning meetings.",
            segment_order=2,
            data_type=DataType.WARM,
            sensitivity_level=2,
            validation_status=ValidationStatus.VALIDATED,
        )
        session.add_all([flagged, ignored_proposed, ignored_mild])
        session.flush()
        for segment in (flagged, ignored_proposed, ignored_mild):
            session.add(
                SegmentTag(
                    segment_id=segment.id,
                    entity_type=EntityType.TEAM_MEMBER,
                    entity_id=member_id,
                    proposed_by=ProposedBy.DWIGHT,
                    confidence=0.9,
                )
            )
        session.commit()

    overview = TobyService(session_factory).overview()

    assert signals_for(overview, member_id) == {"sensitive_warm_segment"}
    signal = next(s for s in overview.signals if s.type == "sensitive_warm_segment")
    assert "1 sensitive observation" in signal.detail


def test_team_trend_averages_moods_per_day(session_factory):
    """Two check-ins the same day average their palette indexes."""
    first = seed_member(session_factory, "Jim")
    second = seed_member(session_factory, "Pam")
    add_checkins(session_factory, first, [(1, MoodLevel.FLOW)])   # index 5
    add_checkins(session_factory, second, [(1, MoodLevel.PRESS)])  # index 2

    overview = TobyService(session_factory).overview()

    assert len(overview.team_trend) == 1
    point = overview.team_trend[0]
    assert point.checkins == 2
    assert point.average_mood_index == 3.5


def test_api_overview_shape(app, client):
    """The HTTP surface exposes window, trend, members and signals."""
    response = client.get("/api/v1/toby/overview", params={"days": 14})
    assert response.status_code == 200
    body = response.json()
    assert body["window_days"] == 14
    assert set(body) >= {"team_trend", "members", "signals", "generated_at"}

def test_voiced_carries_notes_and_validated_warm_quotes(session_factory):
    """The drill-down (recadrage): dated quotes, newest first, gate held."""
    member_id = seed_member(session_factory, "Ryan")
    with session_factory() as session:
        session.add(
            MoodCheckin(
                team_member_id=member_id,
                mood_level=MoodLevel.STUCK,
                note="Long week. Sleeping badly.",
                created_at=utc_naive(2),
            )
        )
        session.add(
            MoodCheckin(
                team_member_id=member_id,
                mood_level=MoodLevel.PRESS,
                note=None,  # no words: nothing to quote
                created_at=utc_naive(1),
            )
        )
        entry = Entry(raw_content="raw", source_type=SourceType.NOTE)
        session.add(entry)
        session.flush()
        validated = EntrySegment(
            entry_id=entry.id,
            content="Seemed on edge, cut Thomas off twice.",
            segment_order=0,
            data_type=DataType.WARM,
            sensitivity_level=3,
            validation_status=ValidationStatus.VALIDATED,
            created_at=utc_naive(5),
        )
        proposed = EntrySegment(
            entry_id=entry.id,
            content="Proposed observation, never validated.",
            segment_order=1,
            data_type=DataType.WARM,
            sensitivity_level=3,
            created_at=utc_naive(4),
        )
        session.add_all([validated, proposed])
        session.flush()
        for segment in (validated, proposed):
            session.add(
                SegmentTag(
                    segment_id=segment.id,
                    entity_type=EntityType.TEAM_MEMBER,
                    entity_id=member_id,
                    proposed_by=ProposedBy.DWIGHT,
                    confidence=0.9,
                )
            )
        session.commit()

    overview = TobyService(session_factory).overview(days=30)
    ryan = next(m for m in overview.members if m.team_member_id == member_id)

    assert [(v.kind, v.text) for v in ryan.voiced] == [
        ("checkin_note", "Long week. Sleeping badly."),
        ("warm_segment", "Seemed on edge, cut Thomas off twice."),
    ]
    assert ryan.voiced[1].sensitivity_level == 3
    # The note travels on the timeline point too.
    assert [p.note for p in ryan.checkins] == ["Long week. Sleeping badly.", None]
