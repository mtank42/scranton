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
    # A birthday is a day, not an age: the year is erased on write.
    assert updated.birthday == date(2000, 2, 14)
    # PUT semantics: null clears.
    cleared = service.update_profile(ids["kelly"], ProfileUpdate())
    assert cleared.personal_profile is None
    assert cleared.birthday is None


def test_profile_update_on_ghost_member_fails(session_factory):
    """404 material: no silent creation of people."""
    with pytest.raises(MemberNotFoundError):
        TeamService(session_factory).update_profile(999, ProfileUpdate())


def test_team_endpoints(member_login, client):
    """HTTP roundtrip: list roster, update YOUR profile (identity session)."""
    member_client, member_id = member_login(name="Kelly")

    roster = client.get("/api/v1/team/members")
    assert roster.status_code == 200
    assert roster.json()[0]["full_name"] == "Kelly"

    updated = member_client.put(
        f"/api/v1/team/members/{member_id}/profile",
        json={"personal_profile": "Collects lip gloss.", "birthday": "1990-02-14"},
    )
    assert updated.status_code == 200
    # Year erased on the wire too: the API never echoes an age back.
    assert updated.json()["birthday"] == "2000-02-14"

    # Someone else's profile - or a ghost's - is a 403 before being a
    # 404: the route only ever accepts YOUR id.
    assert (
        member_client.put("/api/v1/team/members/999/profile", json={}).status_code
        == 403
    )
    # The manager no longer writes profiles on behalf (member-owned).
    assert (
        client.put(
            f"/api/v1/team/members/{member_id}/profile", json={}
        ).status_code
        == 403
    )


def test_roster_is_shaped_by_role(member_login, client):
    """A member sees names, not the room's profiles and birthdays."""
    member_client, member_id = member_login(name="Kelly")
    other_client, other_id = member_login(name="Ryan")
    member_client.put(
        f"/api/v1/team/members/{member_id}/profile",
        json={"personal_profile": "Collects lip gloss.", "birthday": "1990-02-14"},
    )

    # The manager reads the full rows (the profile is shared WITH him).
    manager_view = {m["id"]: m for m in client.get("/api/v1/team/members").json()}
    assert manager_view[member_id]["personal_profile"] == "Collects lip gloss."

    # Another member sees Kelly's name, never her profile fields.
    other_view = {m["id"]: m for m in other_client.get("/api/v1/team/members").json()}
    assert other_view[member_id]["full_name"] == "Kelly"
    assert other_view[member_id]["personal_profile"] is None
    assert other_view[member_id]["birthday"] is None
    # Their own row stays complete.
    kelly_view = {m["id"]: m for m in member_client.get("/api/v1/team/members").json()}
    assert kelly_view[member_id]["personal_profile"] == "Collects lip gloss."