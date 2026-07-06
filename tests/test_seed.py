"""The Dunder Mifflin seeder, on fakes: shape, gates, refusal to mix data."""

from sqlalchemy import func, select

from backend.app.db.seed import SEGMENTS, TEAM, seed
from backend.app.domain.models import (
    EntrySegment,
    MoodCheckin,
    TeamMember,
    ValidationStatus,
)
from tests.conftest import FakeVectorStore, ScriptedLLMProvider


def run_seed(session_factory):
    """Run the seeder with fakes, returning the fakes for assertions."""
    llm = ScriptedLLMProvider([])
    store = FakeVectorStore()
    message = seed(session_factory, llm, store)
    return message, llm, store


def test_seed_populates_the_full_dataset(session_factory):
    """Roster, history and check-ins land; message reports the counts."""
    message, llm, store = run_seed(session_factory)

    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(TeamMember)) == len(TEAM)
        assert session.scalar(select(func.count()).select_from(EntrySegment)) == len(SEGMENTS)
        checkins = session.scalar(select(func.count()).select_from(MoodCheckin))
        assert checkins > 50
    assert "Seeded" in message


def test_only_validated_segments_are_embedded(session_factory):
    """The Ask Pam gate holds in the seeder too: proposed stays out."""
    _, llm, store = run_seed(session_factory)

    validated_count = len([s for s in SEGMENTS if s[5]])
    assert len(store.upserted) == validated_count
    # One batched embed call for everything: no per-segment round-trips.
    assert len(llm.embed_calls) == 1
    with session_factory() as session:
        proposed = session.scalars(
            select(EntrySegment.id).where(
                EntrySegment.validation_status == ValidationStatus.PROPOSED
            )
        ).all()
    embedded_ids = {vector.segment_id for vector in store.upserted}
    assert embedded_ids.isdisjoint(proposed)


def test_seed_refuses_a_non_empty_roster(session_factory):
    """Never silently mix demo data with real data."""
    run_seed(session_factory)
    message, llm, store = run_seed(session_factory)

    assert "skipping" in message
    assert store.upserted == []
    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(TeamMember)) == len(TEAM)


def test_seeded_storylines_feed_toby_signals(session_factory):
    """The dataset is demo material: Ryan declines, Darryl goes silent."""
    from backend.app.services.toby_service import TobyService

    run_seed(session_factory)
    overview = TobyService(session_factory).overview(days=90)

    by_name = {
        signal.member_name: set()
        for signal in overview.signals
    }
    for signal in overview.signals:
        by_name[signal.member_name].add(signal.type)

    assert {"declining_mood", "low_mood", "sensitive_warm_segment"} <= by_name["Ryan"]
    assert "no_recent_checkin" in by_name["Darryl"]
    assert "Oscar" not in by_name  # steady member, zero alarms