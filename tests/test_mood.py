"""Pretzel Day: recording and listing check-ins (service + API)."""

import pytest

from backend.app.domain.models import MoodLevel, TeamMember
from backend.app.domain.schemas import MoodCheckinCreate
from backend.app.services.mood_service import MemberNotFoundError, MoodService


def seed_member(session_factory, name: str = "Pam") -> int:
    """Insert one team member and return its id."""
    with session_factory() as session:
        member = TeamMember(full_name=name, role="Office administrator")
        session.add(member)
        session.commit()
        return member.id


def test_record_and_list_checkins(session_factory):
    """A recorded check-in comes back in the history, oldest first."""
    member_id = seed_member(session_factory)
    service = MoodService(session_factory=session_factory)

    service.record_checkin(
        MoodCheckinCreate(team_member_id=member_id, mood_level=MoodLevel.PRESS)
    )
    service.record_checkin(
        MoodCheckinCreate(
            team_member_id=member_id, mood_level=MoodLevel.FLOW, note="shipped it"
        )
    )

    history = service.list_checkins(member_id=member_id)
    assert [checkin.mood_level for checkin in history] == [
        MoodLevel.PRESS,
        MoodLevel.FLOW,
    ]
    assert history[1].note == "shipped it"


def test_checkin_for_unknown_member_fails_cleanly(session_factory):
    """Unknown member raises the domain error the API maps to 404."""
    service = MoodService(session_factory=session_factory)
    with pytest.raises(MemberNotFoundError):
        service.record_checkin(
            MoodCheckinCreate(team_member_id=999, mood_level=MoodLevel.FLOW)
        )


def test_api_checkin_roundtrip(app, client):
    """POST then GET through HTTP, including the palette value wire format."""
    member_id = seed_member(app.state.session_factory)

    created = client.post(
        "/api/v1/mood/checkins",
        json={"team_member_id": member_id, "mood_level": "pretzel_day"},
    )
    assert created.status_code == 201
    assert created.json()["mood_level"] == "pretzel_day"

    listed = client.get("/api/v1/mood/checkins", params={"member_id": member_id})
    assert listed.status_code == 200
    assert len(listed.json()) == 1


def test_api_unknown_member_is_404_and_bad_level_is_422(app, client):
    """Error contract: missing member 404, invalid palette value 422."""
    assert (
        client.post(
            "/api/v1/mood/checkins", json={"team_member_id": 999, "mood_level": "flow"}
        ).status_code
        == 404
    )
    member_id = seed_member(app.state.session_factory)
    assert (
        client.post(
            "/api/v1/mood/checkins",
            json={"team_member_id": member_id, "mood_level": "angry"},
        ).status_code
        == 422
    )