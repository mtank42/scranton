"""Roster administration: the manager creates and manages the accounts.

Lot 3 of the identity session (2026-07-18). The owner's decisions
(2026-07-14): the manager IS the admin, he creates each collaborator's
account. The onboarding arbitration (2026-07-18): a new account gets a
PROVISIONAL password, shown to the admin exactly once, and the first
login forces a change - the admin never keeps a working credential.

Departures deactivate, never delete (the roster doctrine): flipping
is_active cuts login and revokes every open session at the same
moment, and the handover doctrine covers the data.
"""

import secrets

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from backend.app.domain.models import AuthSession, TeamMember, User, UserRole
from backend.app.domain.schemas import AdminAccountCreated, AdminMemberOut
from backend.app.services.auth_service import (
    _normalize_email,
    hash_password,
    naive_utcnow,
)
from backend.app.services.mood_service import MemberNotFoundError


class EmailTakenError(Exception):
    """The email already belongs to an account (they are logins: unique)."""


def _provisional_password() -> str:
    """A random provisional password the admin can read out loud.

    token_urlsafe(9) gives 12 url-safe characters: strong enough for a
    credential that must die at first login, short enough to dictate
    across a workshop.
    """
    return secrets.token_urlsafe(9)


class AdminService:
    """Create, edit, deactivate and re-open the team's accounts."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        """Wire the only seam this service needs: the database."""
        self.session_factory = session_factory

    def list_accounts(self) -> list[AdminMemberOut]:
        """The WHOLE roster (inactive included) with account status.

        The admin view is the one place departures stay visible: a
        deactivated account must be seen to be reopened.
        """
        with self.session_factory() as session:
            members = session.scalars(
                select(TeamMember).order_by(TeamMember.full_name)
            ).all()
            return [self._shape(session, member) for member in members]

    def create_member(
        self, *, full_name: str, role: str | None, email: str
    ) -> AdminAccountCreated:
        """Create the roster row AND its login account in one gesture.

        Returns the provisional password - the ONLY time it exists in
        clear text. The response is its single exposure: it is never
        stored, never logged, never shown again.
        """
        with self.session_factory() as session:
            self._ensure_email_free(session, email)
            member = TeamMember(full_name=full_name, role=role)
            session.add(member)
            session.flush()
            password = _provisional_password()
            session.add(
                User(
                    email=_normalize_email(email),
                    password_hash=hash_password(password),
                    role=UserRole.MEMBER,
                    team_member_id=member.id,
                    must_change_password=True,
                )
            )
            session.commit()
            return AdminAccountCreated(
                member=self._shape(session, member), provisional_password=password
            )

    def update_member(
        self, member_id: int, *, full_name: str, role: str | None, email: str
    ) -> AdminMemberOut | AdminAccountCreated:
        """Update the professional fields: name, role, login email.

        The member-owned fields (profile, birthday) are NOT here: they
        belong to the member's own Pretzel Day space. A roster row that
        predates the identity session has no account: giving it an
        email HERE creates one (the migration path for existing teams),
        and the result then carries the provisional password.
        """
        with self.session_factory() as session:
            member = self._get_member(session, member_id)
            user = self._get_user(session, member_id)
            self._ensure_email_free(session, email, except_user=user)
            member.full_name = full_name
            member.role = role
            created_password = None
            if user is not None:
                user.email = _normalize_email(email)
            else:
                created_password = _provisional_password()
                session.add(
                    User(
                        email=_normalize_email(email),
                        password_hash=hash_password(created_password),
                        role=UserRole.MEMBER,
                        team_member_id=member.id,
                        must_change_password=True,
                    )
                )
            session.commit()
            shaped = self._shape(session, member)
            if created_password is not None:
                return AdminAccountCreated(
                    member=shaped, provisional_password=created_password
                )
            return shaped

    def set_active(self, member_id: int, active: bool) -> AdminMemberOut:
        """Deactivate (departure) or reactivate a member and their login.

        Deactivation is immediate: the account flips AND every open
        session is revoked, so a departure never stays logged in from
        home. Reactivation reopens login only - dead sessions stay dead.
        """
        with self.session_factory() as session:
            member = self._get_member(session, member_id)
            member.is_active = active
            user = self._get_user(session, member_id)
            if user is not None:
                user.is_active = active
                if not active:
                    self._revoke_sessions(session, user.id)
            session.commit()
            return self._shape(session, member)

    def reset_password(self, member_id: int) -> AdminAccountCreated:
        """New provisional password (forgotten password, day one case).

        Revokes every session and forces the change again. A roster
        row without an account cannot be reset: give it an email first
        (update_member creates the account).
        """
        with self.session_factory() as session:
            member = self._get_member(session, member_id)
            user = self._get_user(session, member_id)
            password = _provisional_password()
            if user is None:
                raise MemberNotFoundError(
                    f"Member {member_id} has no account: set an email first."
                )
            user.password_hash = hash_password(password)
            user.must_change_password = True
            self._revoke_sessions(session, user.id)
            session.commit()
            return AdminAccountCreated(
                member=self._shape(session, member), provisional_password=password
            )

    # --- Internals ---

    @staticmethod
    def _get_member(session: Session, member_id: int) -> TeamMember:
        """The roster row, or the domain error the API maps to 404."""
        member = session.get(TeamMember, member_id)
        if member is None:
            raise MemberNotFoundError(f"No team member with id {member_id}.")
        return member

    @staticmethod
    def _get_user(session: Session, member_id: int) -> User | None:
        """The login account linked to a roster row (None for legacy rows)."""
        return session.scalars(
            select(User).where(User.team_member_id == member_id)
        ).first()

    @staticmethod
    def _ensure_email_free(
        session: Session, email: str, *, except_user: User | None = None
    ) -> None:
        """Emails are logins: refuse a duplicate before SQLite does."""
        existing = session.scalars(
            select(User).where(User.email == _normalize_email(email))
        ).first()
        if existing is not None and existing is not except_user:
            raise EmailTakenError(f"{_normalize_email(email)} already has an account.")

    @staticmethod
    def _revoke_sessions(session: Session, user_id: int) -> None:
        """Kill every open session of a user, now."""
        now = naive_utcnow()
        for record in session.scalars(
            select(AuthSession).where(
                AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None)
            )
        ):
            record.revoked_at = now

    def _shape(self, session: Session, member: TeamMember) -> AdminMemberOut:
        """One admin row: roster fields plus the account's email."""
        user = self._get_user(session, member.id)
        return AdminMemberOut(
            member_id=member.id,
            full_name=member.full_name,
            role=member.role,
            email=user.email if user else None,
            is_active=member.is_active,
            has_account=user is not None,
        )
