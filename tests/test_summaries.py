"""Smart Summaries: the registry, the gathering rules, the honest paths."""

import json
from datetime import datetime, timedelta, timezone

import pytest

from backend.app.domain.models import (
    Client,
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
    ViewType,
)
from backend.app.services.summary_service import (
    NO_MATERIAL_LINE,
    TEMPLATES,
    SummaryService,
    TargetNotFoundError,
    TargetRequiredError,
    UnknownTemplateError,
)
from tests.conftest import ScriptedLLMProvider

MEMBER_FILE_ANSWER = json.dumps(
    {
        "sections": [
            {"heading": "Role and skills", "content": "Senior carpenter [1]."},
            {"heading": "History and contributions", "content": "Finished the Dubreuil kitchen early [2]."},
            {"heading": "Manager observations", "content": "Asked to talk [1]."},
            {"heading": "Signals to watch", "content": NO_MATERIAL_LINE},
        ]
    }
)


def utc_naive(days_ago: int) -> datetime:
    """Naive-UTC timestamp in the past (SQLite storage format)."""
    return datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days_ago)


def add_segment(session, member_id=None, *, content, days_ago=5, warm=False,
                validated=True, view=None, client_id=None, sensitivity=2):
    """One tagged segment with its own entry."""
    entry = Entry(raw_content=content, source_type=SourceType.NOTE)
    session.add(entry)
    session.flush()
    segment = EntrySegment(
        entry_id=entry.id,
        content=content,
        segment_order=0,
        data_type=DataType.WARM if warm else DataType.COLD,
        sensitivity_level=sensitivity,
        validation_status=(
            ValidationStatus.VALIDATED if validated else ValidationStatus.PROPOSED
        ),
        created_at=utc_naive(days_ago),
    )
    session.add(segment)
    session.flush()
    if member_id is not None:
        session.add(SegmentTag(segment_id=segment.id, entity_type=EntityType.TEAM_MEMBER,
                               entity_id=member_id, proposed_by=ProposedBy.DWIGHT, confidence=0.9))
    if client_id is not None:
        session.add(SegmentTag(segment_id=segment.id, entity_type=EntityType.CLIENT,
                               entity_id=client_id, proposed_by=ProposedBy.DWIGHT, confidence=0.9))
    if view is not None:
        session.add(SegmentTag(segment_id=segment.id, entity_type=EntityType.VIEW,
                               entity_id=None, view_type=view,
                               proposed_by=ProposedBy.DWIGHT, confidence=0.9))
    return segment


def make_service(session_factory, completions):
    """A SummaryService on a scripted model."""
    llm = ScriptedLLMProvider(completions)
    return SummaryService(llm=llm, session_factory=session_factory), llm


def test_the_six_templates_are_registered():
    """The registry carries exactly the six living templates."""
    assert set(TEMPLATES) == {
        "team_member_file", "project_file", "client_file",
        "meeting_agenda", "team_radar", "annual_review",
    }


def test_member_file_gathers_segments_profile_and_moods(session_factory):
    """The member file grounds on tagged segments + profile + mood context."""
    with session_factory() as session:
        member = TeamMember(full_name="Kevin", role="Senior carpenter",
                            personal_profile="Fan of New Order")
        session.add(member)
        session.flush()
        member_id = member.id
        add_segment(session, member_id, content="Kevin asked to talk.", days_ago=10, warm=True)
        add_segment(session, member_id, content="Finished the Dubreuil kitchen early.", days_ago=3)
        add_segment(session, member_id, content="Rejected noise.", days_ago=2, validated=False)
        session.add(MoodCheckin(team_member_id=member_id, mood_level=MoodLevel.PRESS,
                                created_at=utc_naive(1)))
        session.commit()

    service, llm = make_service(session_factory, [MEMBER_FILE_ANSWER])
    result = service.generate("team_member_file", member_id)

    assert result.target_label == "Kevin"
    assert [section.heading for section in result.sections] == list(
        TEMPLATES["team_member_file"].sections
    )
    # Sources: validated segments only, chronological, no score.
    assert [source.content for source in result.sources] == [
        "Kevin asked to talk.",
        "Finished the Dubreuil kitchen early.",
    ]
    assert result.sources[0].score is None
    # The model saw the excerpts, the member-owned profile and the moods.
    prompt = llm.complete_calls[0][-1]["content"]
    assert "[1]" in prompt and "asked to talk" in prompt
    assert "member-owned human profile" in prompt and "New Order" in prompt
    assert "mood data" in prompt and "press" in prompt


def test_empty_memory_yields_an_honest_file_without_a_model_call(session_factory):
    """No material: every section says so, zero completion tokens."""
    with session_factory() as session:
        session.add(TeamMember(full_name="Ryan"))
        session.commit()

    service, llm = make_service(session_factory, [])
    result = service.generate("team_member_file", 1)

    assert all(section.content == NO_MATERIAL_LINE for section in result.sections)
    assert result.sources == []
    assert llm.complete_calls == []


def test_meeting_agenda_gathers_by_views_within_window(session_factory):
    """Agenda pulls agenda/CR/commitment views; old and untagged stay out."""
    with session_factory() as session:
        add_segment(session, content="Raise the Q3 pricing.", days_ago=5,
                    view=ViewType.MEETING_AGENDA)
        add_segment(session, content="Promised a revised quote.", days_ago=10,
                    view=ViewType.COMMITMENT)
        add_segment(session, content="Too old to matter.", days_ago=45,
                    view=ViewType.MEETING_AGENDA)
        add_segment(session, content="Unrelated fact.", days_ago=2)
        session.commit()

    service, llm = make_service(
        session_factory,
        [json.dumps({"sections": [{"heading": h, "content": "x [1]"}
                                  for h in TEMPLATES["meeting_agenda"].sections]})],
    )
    result = service.generate("meeting_agenda")

    assert result.target_label is None
    assert [source.content for source in result.sources] == [
        "Promised a revised quote.",
        "Raise the Q3 pricing.",
    ]


def test_team_radar_grounds_on_warm_segments_and_moods(session_factory):
    """The radar reads the warm layer plus the mood aggregates."""
    with session_factory() as session:
        member = TeamMember(full_name="Sonia")
        session.add(member)
        session.flush()
        add_segment(session, member.id, content="Sonia seems exhausted.", days_ago=4,
                    warm=True, sensitivity=4)
        add_segment(session, member.id, content="Cold fact.", days_ago=3)
        session.add(MoodCheckin(team_member_id=member.id, mood_level=MoodLevel.STUCK,
                                created_at=utc_naive(2)))
        session.commit()

    service, llm = make_service(
        session_factory,
        [json.dumps({"sections": [{"heading": h, "content": "y [1]"}
                                  for h in TEMPLATES["team_radar"].sections]})],
    )
    result = service.generate("team_radar")

    assert [source.content for source in result.sources] == ["Sonia seems exhausted."]
    prompt = llm.complete_calls[0][-1]["content"]
    assert "mood data" in prompt and "stuck" in prompt


def test_error_contract(session_factory):
    """Unknown template, missing target, ghost target."""
    service, llm = make_service(session_factory, [])
    with pytest.raises(UnknownTemplateError):
        service.generate("weekly_horoscope")
    with pytest.raises(TargetRequiredError):
        service.generate("team_member_file")
    with pytest.raises(TargetNotFoundError):
        service.generate("team_member_file", 999)


def test_catalog_and_generate_endpoints(app, client):
    """HTTP surface: catalog shape, honest empty generation, error codes."""
    with app.state.session_factory() as session:
        session.add_all([TeamMember(full_name="Kelly"), Client(name="Prince Family Paper")])
        session.commit()

    catalog = client.get("/api/v1/summaries")
    assert catalog.status_code == 200
    body = catalog.json()
    assert len(body["templates"]) == 6
    assert body["targets"]["team_member"][0]["name"] == "Kelly"
    assert body["targets"]["client"][0]["name"] == "Prince Family Paper"

    generated = client.get("/api/v1/summaries/team_member_file", params={"target_id": 1})
    assert generated.status_code == 200
    assert generated.json()["sections"][0]["content"] == NO_MATERIAL_LINE

    assert client.get("/api/v1/summaries/nope").status_code == 404
    assert client.get("/api/v1/summaries/team_member_file").status_code == 422
    assert (
        client.get("/api/v1/summaries/team_member_file", params={"target_id": 99}).status_code
        == 404
    )