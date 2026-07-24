"""Auth foundations: accounts, sessions, first-run setup (identity session).

Service-level tests exercise the logic on an isolated database; API
tests exercise the HTTP contract (cookies included) through the same
TestClient the other surfaces use. No network anywhere: argon2 and
SQLite are all local.
"""

from datetime import date, timedelta

import pytest
from sqlalchemy import select, update

from backend.app.domain.models import BIRTHDAY_YEAR, AuthSession, TeamMember, User, UserRole
from backend.app.services.auth_service import (
    AuthService,
    InvalidCredentialsError,
    SetupAlreadyDoneError,
    hash_password,
    naive_utcnow,
)


@pytest.fixture
def auth(session_factory) -> AuthService:
    """An AuthService on the isolated in-memory schema."""
    return AuthService(session_factory=session_factory, ttl_days=30)


def create_member_account(session_factory, name: str, password: str) -> int:
    """Insert a roster row plus its linked login account; returns user id."""
    with session_factory() as session:
        member = TeamMember(full_name=name, role="Salesman")
        session.add(member)
        session.flush()
        user = User(
            email=f"{name.lower()}@dundermifflin.com",
            password_hash=hash_password(password),
            role=UserRole.MEMBER,
            team_member_id=member.id,
            must_change_password=True,
        )
        session.add(user)
        session.commit()
        return user.id


# --- Service: first run ---


def test_setup_creates_manager_and_opens_session(auth):
    """The first run creates the manager and returns a working token."""
    assert auth.has_manager() is False
    token = auth.create_manager(
        email="Fabrice@Menuiserie.fr",
        password="chene-massif-42",
        full_name="Fabrice",
        birthday=date(1980, 3, 15),
    )
    assert auth.has_manager() is True
    user = auth.current_user(token)
    assert user is not None
    assert user.role == "manager"
    assert user.full_name == "Fabrice"
    # Email normalized: login must not depend on typing case.
    assert user.email == "fabrice@menuiserie.fr"
    # He chose this password himself: nothing to force.
    assert user.must_change_password is False


def test_setup_erases_birthday_year(auth, session_factory):
    """A birthday is a day, never an age: the year is normalized."""
    auth.create_manager(
        email="m@x.fr", password="longenough", full_name="M", birthday=date(1964, 3, 15)
    )
    with session_factory() as session:
        stored = session.scalars(select(User)).one().birthday
    assert stored == date(BIRTHDAY_YEAR, 3, 15)


def test_setup_door_closes_after_first_manager(auth):
    """Once a manager exists, setup can never run again."""
    auth.create_manager(email="m@x.fr", password="longenough", full_name="M")
    with pytest.raises(SetupAlreadyDoneError):
        auth.create_manager(email="other@x.fr", password="longenough", full_name="O")


# --- Service: login and sessions ---


def test_login_failures_raise_one_same_error(auth):
    """Unknown email and wrong password are indistinguishable."""
    auth.create_manager(email="m@x.fr", password="longenough", full_name="M")
    with pytest.raises(InvalidCredentialsError) as unknown:
        auth.login("nobody@x.fr", "whatever-pass")
    with pytest.raises(InvalidCredentialsError) as wrong:
        auth.login("m@x.fr", "wrong-password")
    assert str(unknown.value) == str(wrong.value)


def test_deactivated_user_cannot_login_and_loses_sessions(auth, session_factory):
    """is_active False cuts login and invalidates existing sessions."""
    user_id = create_member_account(session_factory, "Stanley", "pretzelday99")
    token = auth.login("stanley@dundermifflin.com", "pretzelday99")
    assert auth.current_user(token) is not None
    with session_factory() as session:
        session.execute(update(User).where(User.id == user_id).values(is_active=False))
        session.commit()
    assert auth.current_user(token) is None
    with pytest.raises(InvalidCredentialsError):
        auth.login("stanley@dundermifflin.com", "pretzelday99")


def test_member_identity_resolves_roster_name(auth, session_factory):
    """A member's display name comes from the roster row, not users."""
    create_member_account(session_factory, "Phyllis", "pretzelday99")
    token = auth.login("phyllis@dundermifflin.com", "pretzelday99")
    user = auth.current_user(token)
    assert user.full_name == "Phyllis"
    assert user.role == "member"
    assert user.team_member_id is not None
    # Admin-created account: the first login must force a change.
    assert user.must_change_password is True


def test_logout_revokes_the_session(auth):
    """A revoked token resolves to nobody, and logout is idempotent."""
    auth.create_manager(email="m@x.fr", password="longenough", full_name="M")
    token = auth.login("m@x.fr", "longenough")
    auth.logout(token)
    assert auth.current_user(token) is None
    auth.logout(token)  # idempotent: no error on a dead token


def test_expired_session_resolves_to_nobody(auth, session_factory):
    """Past expires_at, the token is dead even if never revoked."""
    auth.create_manager(email="m@x.fr", password="longenough", full_name="M")
    token = auth.login("m@x.fr", "longenough")
    with session_factory() as session:
        session.execute(
            update(AuthSession).values(expires_at=naive_utcnow() - timedelta(days=1))
        )
        session.commit()
    assert auth.current_user(token) is None


def test_change_password_clears_flag_and_revokes_other_sessions(auth, session_factory):
    """The forced first-login change, plus the standard safety reflex."""
    create_member_account(session_factory, "Ryan", "temp-password")
    other_token = auth.login("ryan@dundermifflin.com", "temp-password")
    token = auth.login("ryan@dundermifflin.com", "temp-password")
    user = auth.change_password(token, "temp-password", "my-own-secret")
    assert user.must_change_password is False
    # The session that changed the password survives; the other dies.
    assert auth.current_user(token) is not None
    assert auth.current_user(other_token) is None
    # Old password dead, new one works.
    with pytest.raises(InvalidCredentialsError):
        auth.login("ryan@dundermifflin.com", "temp-password")
    auth.login("ryan@dundermifflin.com", "my-own-secret")


def test_change_password_requires_the_current_one(auth):
    """A valid session alone must not be enough to take over an account."""
    auth.create_manager(email="m@x.fr", password="longenough", full_name="M")
    token = auth.login("m@x.fr", "longenough")
    with pytest.raises(InvalidCredentialsError):
        auth.change_password(token, "not-the-password", "whatever-new")


# --- API: the HTTP contract ---


def test_api_first_run_flow(anon_client):
    """status -> setup -> cookie-backed me -> the door closes."""
    assert anon_client.get("/api/v1/auth/status").json() == {"initialized": False}
    response = anon_client.post(
        "/api/v1/auth/setup",
        json={"email": "m@x.fr", "password": "longenough", "full_name": "Michael"},
    )
    assert response.status_code == 200
    # The TestClient keeps the httponly cookie like a browser would.
    me = anon_client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["role"] == "manager"
    assert anon_client.get("/api/v1/auth/status").json() == {"initialized": True}
    again = anon_client.post(
        "/api/v1/auth/setup",
        json={"email": "x@y.fr", "password": "longenough", "full_name": "X"},
    )
    assert again.status_code == 409


def test_api_me_requires_a_session(anon_client):
    """No cookie, no identity: 401."""
    assert anon_client.get("/api/v1/auth/me").status_code == 401


def test_api_login_logout(anon_client):
    """Login sets the cookie, logout kills it."""
    anon_client.post(
        "/api/v1/auth/setup",
        json={"email": "m@x.fr", "password": "longenough", "full_name": "Michael"},
    )
    anon_client.post("/api/v1/auth/logout")
    assert anon_client.get("/api/v1/auth/me").status_code == 401
    bad = anon_client.post(
        "/api/v1/auth/login", json={"email": "m@x.fr", "password": "wrong-pass"}
    )
    assert bad.status_code == 401
    good = anon_client.post(
        "/api/v1/auth/login", json={"email": "M@X.FR", "password": "longenough"}
    )
    assert good.status_code == 200
    assert anon_client.get("/api/v1/auth/me").status_code == 200


def test_api_change_password(anon_client):
    """Wrong current password is a 400; the session stays valid."""
    anon_client.post(
        "/api/v1/auth/setup",
        json={"email": "m@x.fr", "password": "longenough", "full_name": "Michael"},
    )
    bad = anon_client.post(
        "/api/v1/auth/change-password",
        json={"current_password": "nope-nope", "new_password": "brand-new-pass"},
    )
    assert bad.status_code == 400
    good = anon_client.post(
        "/api/v1/auth/change-password",
        json={"current_password": "longenough", "new_password": "brand-new-pass"},
    )
    assert good.status_code == 200
    assert anon_client.get("/api/v1/auth/me").status_code == 200


def test_api_short_password_rejected(anon_client):
    """The 8-character floor is enforced at the schema edge (422)."""
    response = anon_client.post(
        "/api/v1/auth/setup",
        json={"email": "m@x.fr", "password": "short", "full_name": "Michael"},
    )
    assert response.status_code == 422


# --- The scoping map (lot 2): who reaches what ---


def test_manager_surfaces_refuse_members_and_anonymous(member_login, anon_client):
    """The owner's scoping list, enforced server-side.

    One representative route per manager-only surface: Toby (warm
    layer), the Desk briefs and generation, Darryl's archive, the
    edited documents, handover, exports. Tell Dwight is NOT here: the
    capture pipeline belongs to the whole team (owner, 2026-07-19).
    """
    member_client, _ = member_login()
    manager_only = [
        ("GET", "/api/v1/toby/overview"),
        ("GET", "/api/v1/summaries/weekly_review"),
        ("GET", "/api/v1/darryl/documents/recent"),
        ("GET", "/api/v1/documents"),
        ("GET", "/api/v1/handover/1"),
        ("GET", "/api/v1/angela/export/weekly_review"),
    ]
    for method, path in manager_only:
        assert member_client.request(method, path).status_code == 403, path
        assert anon_client.request(method, path).status_code == 401, path


def test_shared_surfaces_require_a_session(member_login, anon_client):
    """Pam, Dwight's thread, the catalog, the mayor and the roster:
    any logged-in user, but never anonymous."""
    member_client, _ = member_login()
    shared = [
        ("GET", "/api/v1/team/mayor"),
        ("GET", "/api/v1/team/members"),
        ("GET", "/api/v1/summaries"),
        ("GET", "/api/v1/mood/checkins"),
        ("GET", "/api/v1/dwight/entries/recent"),
    ]
    for method, path in shared:
        assert member_client.request(method, path).status_code == 200, path
        assert anon_client.request(method, path).status_code == 401, path
    # The UI branding and liveness stay public: the login page needs them.
    assert anon_client.get("/api/v1/config/ui").status_code == 200
    assert anon_client.get("/api/v1/health").status_code == 200
