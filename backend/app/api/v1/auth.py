"""Auth endpoints: first-run setup, login, logout, password change.

The HTTP layer of the identity session (2026-07-18). The session rides
in an httponly cookie: the frontend never sees or stores the token,
which takes the whole class of script-steals-token bugs off the table.
"""

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from backend.app.api.deps import (
    SESSION_COOKIE,
    get_auth_service,
    get_current_user,
)
from backend.app.config import get_settings
from backend.app.domain.schemas import (
    AuthStatus,
    ChangePasswordIn,
    CurrentUserOut,
    LoginIn,
    SetupIn,
)
from backend.app.services.auth_service import (
    AuthService,
    InvalidCredentialsError,
    SetupAlreadyDoneError,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def _set_session_cookie(response: Response, token: str) -> None:
    """Attach the session token to the response, hardened.

    httponly: no script access. samesite=lax: the cookie never rides a
    cross-site POST. secure comes from settings: False on the MVP's
    plain-HTTP local network, True on any hosted deployment.
    """
    settings = get_settings()
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=settings.session_ttl_days * 24 * 3600,
        httponly=True,
        samesite="lax",
        secure=settings.session_cookie_secure,
    )


@router.get("/status", response_model=AuthStatus)
def auth_status(service: AuthService = Depends(get_auth_service)) -> AuthStatus:
    """Whether the first-run setup happened (public: the landing needs it)."""
    return AuthStatus(initialized=service.has_manager())


@router.post("/setup", response_model=CurrentUserOut)
def setup(
    payload: SetupIn,
    response: Response,
    service: AuthService = Depends(get_auth_service),
) -> CurrentUserOut:
    """First run: create THE manager account and log him in.

    409 once a manager exists: the endpoint is a one-time door, never a
    way to add accounts (that is the admin surface, manager-only).
    """
    try:
        token = service.create_manager(
            email=payload.email,
            password=payload.password,
            full_name=payload.full_name,
            birthday=payload.birthday,
        )
    except SetupAlreadyDoneError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    _set_session_cookie(response, token)
    user = service.current_user(token)
    assert user is not None  # the token was just created
    return user


@router.post("/login", response_model=CurrentUserOut)
def login(
    payload: LoginIn,
    response: Response,
    service: AuthService = Depends(get_auth_service),
) -> CurrentUserOut:
    """Open a session. One 401 for every failure cause (no probing)."""
    try:
        token = service.login(payload.email, payload.password)
    except InvalidCredentialsError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))
    _set_session_cookie(response, token)
    user = service.current_user(token)
    assert user is not None  # the token was just created
    return user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    request: Request,
    response: Response,
    service: AuthService = Depends(get_auth_service),
) -> None:
    """Revoke the session and drop the cookie (idempotent)."""
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        service.logout(token)
    response.delete_cookie(SESSION_COOKIE)


@router.get("/me", response_model=CurrentUserOut)
def me(user: CurrentUserOut = Depends(get_current_user)) -> CurrentUserOut:
    """The logged-in identity (the frontend boots from this)."""
    return user


@router.post("/change-password", response_model=CurrentUserOut)
def change_password(
    payload: ChangePasswordIn,
    request: Request,
    service: AuthService = Depends(get_auth_service),
    user: CurrentUserOut = Depends(get_current_user),
) -> CurrentUserOut:
    """Change the password behind the current session.

    get_current_user guarantees a valid session; a wrong CURRENT
    password is then a 400 (bad request), not a 401 (the session
    itself is fine).
    """
    token = request.cookies.get(SESSION_COOKIE)
    assert token is not None  # get_current_user already required it
    try:
        return service.change_password(
            token, payload.current_password, payload.new_password
        )
    except InvalidCredentialsError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect.",
        )
