"""Admin surface: the manager creates and manages the team's accounts.

Lot 3 of the identity session. The flows under test are the owner's
day-one use case: create Kevin (provisional password, shown once),
Kevin leaves (deactivate: login cut, sessions dead), Kevin forgot his
password (reset), and the pre-identity roster row that gains an
account through an email.
"""

from datetime import date

from backend.app.domain.models import BIRTHDAY_YEAR, TeamMember, User, UserRole
from backend.app.services.team_service import TeamService


def test_create_member_returns_a_one_time_password(client):
    """One gesture creates the roster row and the login account."""
    created = client.post(
        "/api/v1/admin/members",
        json={"full_name": "Kevin", "role": "Senior carpenter", "email": "kevin@x.fr"},
    )
    assert created.status_code == 201
    body = created.json()
    assert body["member"]["email"] == "kevin@x.fr"
    assert body["member"]["has_account"] is True
    password = body["provisional_password"]
    assert len(password) >= 8

    # The password works exactly as designed: login, then forced change.
    from fastapi.testclient import TestClient

    kevin = TestClient(client.app)
    logged = kevin.post(
        "/api/v1/auth/login", json={"email": "kevin@x.fr", "password": password}
    )
    assert logged.status_code == 200
    assert logged.json()["must_change_password"] is True


def test_duplicate_email_is_a_conflict(client):
    """Emails are logins: unique, told cleanly."""
    payload = {"full_name": "Kevin", "email": "kevin@x.fr"}
    assert client.post("/api/v1/admin/members", json=payload).status_code == 201
    again = client.post(
        "/api/v1/admin/members", json={"full_name": "Other", "email": "KEVIN@x.fr"}
    )
    assert again.status_code == 409


def test_deactivate_cuts_login_and_sessions(client, member_login):
    """A departure: login refused, the open session dies immediately."""
    member_client, member_id = member_login(name="Stanley")
    assert member_client.get("/api/v1/auth/me").status_code == 200

    done = client.post(f"/api/v1/admin/members/{member_id}/deactivate")
    assert done.status_code == 200
    assert done.json()["is_active"] is False
    assert member_client.get("/api/v1/auth/me").status_code == 401
    refused = member_client.post(
        "/api/v1/auth/login",
        json={"email": "stanley@test.local", "password": "pretzelday99"},
    )
    assert refused.status_code == 401

    # Reactivation reopens login; the old session stays dead.
    client.post(f"/api/v1/admin/members/{member_id}/reactivate")
    assert member_client.get("/api/v1/auth/me").status_code == 401
    back = member_client.post(
        "/api/v1/auth/login",
        json={"email": "stanley@test.local", "password": "pretzelday99"},
    )
    assert back.status_code == 200


def test_reset_password_revokes_and_forces_change(client, member_login):
    """The forgotten-password path, admin-side."""
    member_client, member_id = member_login(name="Ryan")
    reset = client.post(f"/api/v1/admin/members/{member_id}/reset-password")
    assert reset.status_code == 200
    password = reset.json()["provisional_password"]
    # The old session is gone, the old password too.
    assert member_client.get("/api/v1/auth/me").status_code == 401
    assert (
        member_client.post(
            "/api/v1/auth/login",
            json={"email": "ryan@test.local", "password": "pretzelday99"},
        ).status_code
        == 401
    )
    logged = member_client.post(
        "/api/v1/auth/login", json={"email": "ryan@test.local", "password": password}
    )
    assert logged.status_code == 200
    assert logged.json()["must_change_password"] is True


def test_update_creates_the_missing_account(app, client):
    """A pre-identity roster row gains its account through an email."""
    with app.state.session_factory() as session:
        member = TeamMember(full_name="Phyllis", role="Saleswoman")
        session.add(member)
        session.commit()
        member_id = member.id

    listed = {m["member_id"]: m for m in client.get("/api/v1/admin/members").json()}
    assert listed[member_id]["has_account"] is False

    updated = client.put(
        f"/api/v1/admin/members/{member_id}",
        json={"full_name": "Phyllis", "role": "Saleswoman", "email": "phyllis@x.fr"},
    )
    assert updated.status_code == 200
    body = updated.json()
    assert body["member"]["has_account"] is True
    assert "provisional_password" in body


def test_admin_is_manager_only(member_login, anon_client):
    """The scoping rule applies to the admin surface itself."""
    member_client, _ = member_login()
    assert member_client.get("/api/v1/admin/members").status_code == 403
    assert anon_client.get("/api/v1/admin/members").status_code == 401


def test_manager_is_eligible_mayor(app, client):
    """Owner decision 2026-07-14: the manager can be Maire de Scranton.

    His birthday lives on the users row (identity apart); the ritual
    reads it alongside the roster.
    """
    today = date.today()
    with app.state.session_factory() as session:
        manager = session.query(User).filter(User.role == UserRole.MANAGER).one()
        manager.birthday = today.replace(year=BIRTHDAY_YEAR)
        session.commit()
    service = TeamService(session_factory=app.state.session_factory)
    overview = service.mayor_overview(today=today)
    assert overview.mayor is not None
    assert overview.mayor.full_name == "Test Manager"
