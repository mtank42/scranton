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


def test_api_checkin_roundtrip(member_login, client):
    """POST then GET through HTTP, including the palette value wire format.

    A check-in is a member gesture since the identity session: the
    member posts for themself, the manager reads the history.
    """
    member_client, member_id = member_login()

    created = member_client.post(
        "/api/v1/mood/checkins",
        json={"team_member_id": member_id, "mood_level": "pretzel_day"},
    )
    assert created.status_code == 201
    assert created.json()["mood_level"] == "pretzel_day"

    listed = client.get("/api/v1/mood/checkins", params={"member_id": member_id})
    assert listed.status_code == 200
    assert len(listed.json()) == 1


def test_api_checkin_is_always_your_own(member_login, client):
    """The session identity rules: someone else's id is a 403, the
    manager (no member self) is a 403, a bad palette value stays 422."""
    member_client, member_id = member_login()
    assert (
        member_client.post(
            "/api/v1/mood/checkins", json={"team_member_id": 999, "mood_level": "flow"}
        ).status_code
        == 403
    )
    # The manager has no mood tracking (owner decision 2026-07-14).
    assert (
        client.post(
            "/api/v1/mood/checkins",
            json={"team_member_id": member_id, "mood_level": "flow"},
        ).status_code
        == 403
    )
    assert (
        member_client.post(
            "/api/v1/mood/checkins",
            json={"team_member_id": member_id, "mood_level": "angry"},
        ).status_code
        == 422
    )


def test_api_member_history_is_forced_to_self(member_login):
    """Whatever the query says, a member only reads their own history."""
    member_client, member_id = member_login()
    other_client, other_id = member_login(name="Kelly")
    member_client.post(
        "/api/v1/mood/checkins",
        json={"team_member_id": member_id, "mood_level": "flow"},
    )
    other_client.post(
        "/api/v1/mood/checkins",
        json={"team_member_id": other_id, "mood_level": "stuck"},
    )
    listed = other_client.get(
        "/api/v1/mood/checkins", params={"member_id": member_id}
    )
    assert listed.status_code == 200
    assert [checkin["team_member_id"] for checkin in listed.json()] == [other_id]