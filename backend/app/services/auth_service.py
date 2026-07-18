"""Accounts and sessions: who may enter Scranton, and who is in.

The privacy-first pivot (identity session, 2026-07-18): every person
logs in from their own machine, so identity becomes something you PROVE
(a password) instead of something you declare (the POC's identity
picker). Two building blocks live here:

- Passwords: argon2id hashes, never the password itself. argon2 is
  memory-hard and slow on purpose, which is exactly what you want when
  a database leaks.
- Sessions: an opaque random token in a cookie; the database stores
  only its SHA-256. A stolen database therefore contains nothing that
  logs anyone in - neither passwords nor usable tokens.

Every datetime handled here is NAIVE UTC, because that is how SQLite
stores them (CLAUDE.md gotcha): mixing aware and naive datetimes raises
at comparison time.
"""

import hashlib
import secrets
from datetime import date, datetime, timedelta, timezone

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from backend.app.domain.models import BIRTHDAY_YEAR, AuthSession, User, UserRole
from backend.app.domain.schemas import CurrentUserOut

# One module-level hasher: argon2id with the library's vetted defaults.
# Tuning the parameters is a security decision, not a config knob.
_hasher = PasswordHasher()


class AuthError(Exception):
    """Base class for authentication failures."""


class InvalidCredentialsError(AuthError):
    """Login refused. One error for every cause (unknown email, wrong
    password, deactivated account): a distinct message per cause would
    let anyone probe which emails have an account."""


class SetupAlreadyDoneError(AuthError):
    """The first-run door is closed: a manager account already exists."""


def hash_password(password: str) -> str:
    """Hash a password with argon2id (module seam, reused by the seed)."""
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """True if the password matches the stored hash."""
    try:
        return _hasher.verify(password_hash, password)
    except VerifyMismatchError:
        return False


def naive_utcnow() -> datetime:
    """Naive UTC now, matching what SQLite stores (CLAUDE.md gotcha)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _hash_token(token: str) -> str:
    """SHA-256 of a session token: what the database is allowed to see.

    Unlike passwords, tokens are long random secrets, so a fast hash is
    fine here: there is nothing human-guessable to brute-force.
    """
    return hashlib.sha256(token.encode()).hexdigest()


class AuthService:
    """Create accounts, open and close sessions, resolve who is in."""

    def __init__(self, session_factory: sessionmaker[Session], *, ttl_days: int = 30) -> None:
        """Wire the database seam and the session lifetime (a setting)."""
        self.session_factory = session_factory
        self.ttl_days = ttl_days

    # --- First run ---

    def has_manager(self) -> bool:
        """Whether the first-run setup already happened.

        The landing page uses this to decide what to show: the setup
        screen (no manager yet) or the login form.
        """
        with self.session_factory() as session:
            return self._manager_exists(session)

    def create_manager(
        self,
        *,
        email: str,
        password: str,
        full_name: str,
        birthday: date | None = None,
    ) -> str:
        """First-run setup: create THE manager account and log him in.

        The door closes itself: once a manager exists this raises, so
        the setup endpoint can never become a privilege escalation.
        Returns a session token (the setup flows straight into a
        logged-in state: asking the founder to retype his password
        would be pure friction).
        """
        with self.session_factory() as session:
            if self._manager_exists(session):
                raise SetupAlreadyDoneError("A manager account already exists.")
            user = User(
                email=_normalize_email(email),
                password_hash=hash_password(password),
                role=UserRole.MANAGER,
                full_name=full_name,
                # A birthday is a day, never an age: year erased, as
                # everywhere else (the manager is eligible Maire).
                birthday=birthday.replace(year=BIRTHDAY_YEAR) if birthday else None,
                # He chose this password himself: nothing to force.
                must_change_password=False,
            )
            session.add(user)
            session.flush()
            token = self._open_session(session, user.id)
            session.commit()
            return token

    # --- Login / logout ---

    def login(self, email: str, password: str) -> str:
        """Verify credentials and open a session; returns the token.

        Every failure raises the SAME error (see
        InvalidCredentialsError): the response never reveals whether an
        email has an account.
        """
        with self.session_factory() as session:
            user = session.scalars(
                select(User).where(User.email == _normalize_email(email))
            ).first()
            if user is None or not user.is_active:
                raise InvalidCredentialsError("Invalid email or password.")
            if not verify_password(password, user.password_hash):
                raise InvalidCredentialsError("Invalid email or password.")
            token = self._open_session(session, user.id)
            session.commit()
            return token

    def logout(self, token: str) -> None:
        """Revoke the session behind this token (idempotent)."""
        with self.session_factory() as session:
            record = self._find_session(session, token)
            if record is not None and record.revoked_at is None:
                record.revoked_at = naive_utcnow()
                session.commit()

    # --- Who is in ---

    def current_user(self, token: str | None) -> CurrentUserOut | None:
        """Resolve a cookie token to the logged-in user, or None.

        None for every dead end (no cookie, unknown token, revoked or
        expired session, deactivated user): the caller only needs to
        know whether someone valid is behind the request.
        """
        if not token:
            return None
        with self.session_factory() as session:
            record = self._find_session(session, token)
            if record is None or record.revoked_at is not None:
                return None
            if record.expires_at < naive_utcnow():
                return None
            user = session.get(User, record.user_id)
            if user is None or not user.is_active:
                return None
            return _to_current_user(user)

    # --- Password change ---

    def change_password(self, token: str, current_password: str, new_password: str) -> CurrentUserOut:
        """Change the logged-in user's password.

        Requires the current password even with a valid session: an
        unattended machine must not be enough to lock someone out of
        their own account. Clears must_change_password (this IS the
        forced first-login change) and revokes every OTHER session:
        changing a password is the standard reflex after a doubt, so it
        must cut any session the doubt is about.
        """
        with self.session_factory() as session:
            record = self._find_session(session, token)
            if record is None:
                raise InvalidCredentialsError("Invalid email or password.")
            user = session.get(User, record.user_id)
            if user is None or not verify_password(current_password, user.password_hash):
                raise InvalidCredentialsError("Invalid email or password.")
            user.password_hash = hash_password(new_password)
            user.must_change_password = False
            now = naive_utcnow()
            others = session.scalars(
                select(AuthSession).where(
                    AuthSession.user_id == user.id,
                    AuthSession.id != record.id,
                    AuthSession.revoked_at.is_(None),
                )
            ).all()
            for other in others:
                other.revoked_at = now
            session.commit()
            return _to_current_user(user)

    # --- Internals ---

    def _open_session(self, session: Session, user_id: int) -> str:
        """Create a session row and return the raw token (cookie value)."""
        token = secrets.token_urlsafe(32)
        session.add(
            AuthSession(
                token_hash=_hash_token(token),
                user_id=user_id,
                expires_at=naive_utcnow() + timedelta(days=self.ttl_days),
            )
        )
        return token

    @staticmethod
    def _find_session(session: Session, token: str) -> AuthSession | None:
        """Look up a session row by the hash of its token."""
        return session.scalars(
            select(AuthSession).where(AuthSession.token_hash == _hash_token(token))
        ).first()

    @staticmethod
    def _manager_exists(session: Session) -> bool:
        """Whether any manager account exists (active or not)."""
        return (
            session.scalars(select(User).where(User.role == UserRole.MANAGER)).first()
            is not None
        )


def _normalize_email(email: str) -> str:
    """Lowercase and trim: logins must not depend on typing case."""
    return email.strip().lower()


def _to_current_user(user: User) -> CurrentUserOut:
    """Shape a User row for the API, resolving the display name.

    A member's name lives on their roster row (single source of truth);
    only the manager carries full_name on the users table.
    """
    name = user.full_name
    if user.team_member is not None:
        name = user.team_member.full_name
    return CurrentUserOut(
        id=user.id,
        email=user.email,
        role=user.role.value,
        full_name=name,
        team_member_id=user.team_member_id,
        must_change_password=user.must_change_password,
    )
