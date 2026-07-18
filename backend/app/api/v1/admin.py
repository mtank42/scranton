"""Admin endpoints: the manager manages the team's accounts.

Lot 3 of the identity session. Everything here is manager-only by
construction (the guard rides the router): creating people, cutting
access and resetting passwords are exactly the gestures the scoping
exists for.
"""

from fastapi import APIRouter, Depends, HTTPException, status

from backend.app.api.deps import get_admin_service, require_manager
from backend.app.domain.schemas import (
    AdminAccountCreated,
    AdminMemberCreate,
    AdminMemberOut,
    AdminMemberUpdate,
)
from backend.app.services.admin_service import AdminService, EmailTakenError
from backend.app.services.mood_service import MemberNotFoundError

router = APIRouter(
    prefix="/admin", tags=["admin"], dependencies=[Depends(require_manager)]
)


@router.get("/members", response_model=list[AdminMemberOut])
def list_accounts(service: AdminService = Depends(get_admin_service)) -> list[AdminMemberOut]:
    """The whole roster with account status, departures included."""
    return service.list_accounts()


@router.post("/members", response_model=AdminAccountCreated, status_code=status.HTTP_201_CREATED)
def create_member(
    payload: AdminMemberCreate,
    service: AdminService = Depends(get_admin_service),
) -> AdminAccountCreated:
    """Create a member and their account; returns the one-time password."""
    try:
        return service.create_member(
            full_name=payload.full_name, role=payload.role, email=payload.email
        )
    except EmailTakenError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


@router.put("/members/{member_id}", response_model=AdminMemberOut | AdminAccountCreated)
def update_member(
    member_id: int,
    payload: AdminMemberUpdate,
    service: AdminService = Depends(get_admin_service),
) -> AdminMemberOut | AdminAccountCreated:
    """Update name, role and login email.

    Giving an email to a pre-identity roster row creates its account:
    the response then carries the one-time provisional password.
    """
    try:
        return service.update_member(
            member_id,
            full_name=payload.full_name,
            role=payload.role,
            email=payload.email,
        )
    except MemberNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except EmailTakenError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


@router.post("/members/{member_id}/deactivate", response_model=AdminMemberOut)
def deactivate_member(
    member_id: int,
    service: AdminService = Depends(get_admin_service),
) -> AdminMemberOut:
    """A departure: login cut, sessions revoked, data kept (doctrine)."""
    try:
        return service.set_active(member_id, False)
    except MemberNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.post("/members/{member_id}/reactivate", response_model=AdminMemberOut)
def reactivate_member(
    member_id: int,
    service: AdminService = Depends(get_admin_service),
) -> AdminMemberOut:
    """Reopen a deactivated member's login (old sessions stay dead)."""
    try:
        return service.set_active(member_id, True)
    except MemberNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.post("/members/{member_id}/reset-password", response_model=AdminAccountCreated)
def reset_password(
    member_id: int,
    service: AdminService = Depends(get_admin_service),
) -> AdminAccountCreated:
    """New one-time provisional password; every session is revoked."""
    try:
        return service.reset_password(member_id)
    except MemberNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
