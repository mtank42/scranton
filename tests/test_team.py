"""The team roster and the member-owned human profile."""

from datetime import date

import pytest

from backend.app.domain.models import TeamMember
from backend.app.domain.schemas import ProfileUpdate
from backend.app.services.mood_service import MemberNotFoundError
from backend.app.services.team_service import TeamService


def seed_roster(session_factory) -> dict[str, int]:
    """Two active members and one departed, returned by name."""
    with session_factory() as session:
        active = TeamMember(full_name="Kelly", role="Customer service")
        other = TeamMember(full_name="Darryl", role="Warehouse foreman")
        gone = TeamMember(full_name="Creed", is_active=False)
        session.add_all([active, other, gone])
        session.commit()
        return {"kelly": active.id, "darryl": other.id, "creed": gone.id}


def test_roster_lists_active_members_only(session_factory):
    """Departures (is_active=False) never disappear from the db, only from the roster."""
    seed_roster(session_factory)
    members = TeamService(session_factory).list_members()
    assert [member.full_name for member in members] == ["Darryl", "Kelly"]


def test_profile_update_roundtrip(session_factory):
    """The member-owned fields persist and come back."""
    ids = seed_roster(session_factory)
    service = TeamService(session_factory)

    updated = service.update_profile(
        ids["kelly"],
        ProfileUpdate(
            personal_profile="Loves romantic comedies.",
            birthday=date(1990, 2, 14),
        ),
    )

    assert updated.personal_profile == "Loves romantic comedies."
    assert updated.birthday == date(1990, 2, 14)
    # PUT semantics: null clears.
    cleared = service.update_profile(ids["kelly"], ProfileUpdate())
    assert cleared.personal_profile is None
    assert cleared.birthday is None


def test_profile_update_on_ghost_member_fails(session_factory):
    """404 material: no silent creation of people."""
    with pytest.raises(MemberNotFoundError):
        TeamService(session_factory).update_profile(999, ProfileUpdate())


def test_team_endpoints(app, client):
    """HTTP roundtrip: list roster, update a profile, 404 on ghosts."""
    with app.state.session_factory() as session:
        member = TeamMember(full_name="Kelly", role="Customer service")
        session.add(member)
        session.commit()
        member_id = member.id

    roster = client.get("/api/v1/team/members")
    assert roster.status_code == 200
    assert roster.json()[0]["full_name"] == "Kelly"

    updated = client.put(
        f"/api/v1/team/members/{member_id}/profile",
        json={"personal_profile": "Collects lip gloss.", "birthday": "1990-02-14"},
    )
    assert updated.status_code == 200
    assert updated.json()["birthday"] == "1990-02-14"

    assert (
        client.put("/api/v1/team/members/999/profile", json={}).status_code == 404
    )