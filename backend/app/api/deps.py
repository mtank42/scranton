"""FastAPI dependencies: assemble services from the app state.

The lifespan hook (main.py) builds the shared adapters once and parks
them on app.state. Dependencies only assemble: this is what lets tests
swap any seam through app.dependency_overrides without patching.
"""

from fastapi import Depends, HTTPException, Request, status

from backend.app.adapters.documents.factory import build_document_source
from backend.app.adapters.ingestion.factory import build_ingestion_source
from backend.app.config import get_settings
from backend.app.domain.schemas import CurrentUserOut
from backend.app.services.admin_service import AdminService
from backend.app.services.angela_service import AngelaService
from backend.app.services.auth_service import AuthService
from backend.app.services.darryl_service import DarrylService
from backend.app.services.dwight_service import DwightService
from backend.app.services.editing_service import EditingService
from backend.app.services.handover_service import HandoverService
from backend.app.services.ingestion_service import IngestionService
from backend.app.services.mood_service import MoodService
from backend.app.services.pam_service import PamService
from backend.app.services.summary_service import SummaryService
from backend.app.services.team_service import TeamService
from backend.app.services.toby_service import TobyService


# The session cookie (identity session, 2026-07-18). Lives here, next
# to the dependencies that read it: routers import the name, never
# hardcode the string.
SESSION_COOKIE = "scranton_session"


def get_auth_service(request: Request) -> AuthService:
    """Build an AuthService wired to the app-level session factory."""
    return AuthService(
        session_factory=request.app.state.session_factory,
        ttl_days=get_settings().session_ttl_days,
    )


def get_admin_service(request: Request) -> AdminService:
    """Build an AdminService wired to the app-level session factory."""
    return AdminService(session_factory=request.app.state.session_factory)


def get_current_user(
    request: Request,
    service: AuthService = Depends(get_auth_service),
) -> CurrentUserOut:
    """The logged-in user behind the request's cookie, or 401.

    This is the foundation the per-role guards build on (lot 2 of the
    identity session): a route that depends on this cannot be reached
    anonymously.
    """
    user = service.current_user(request.cookies.get(SESSION_COOKIE))
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Not logged in."
        )
    return user


def require_manager(
    user: CurrentUserOut = Depends(get_current_user),
) -> CurrentUserOut:
    """Manager-only gate (lot 2 of the identity session).

    Until now 'manager-only' was a UI intention anyone could flip; this
    dependency makes it a server fact: the warm layer (Toby, the Desk),
    the corpus surfaces and the capture pipeline answer 403 to members.
    """
    if user.role != "manager":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Manager only."
        )
    return user


def require_member(
    user: CurrentUserOut = Depends(get_current_user),
) -> CurrentUserOut:
    """Member-self gate: actions that only make sense FOR YOURSELF.

    Pretzel Day check-ins and the personal profile are member-owned
    (data ownership split): the manager has no mood tracking (owner
    decision 2026-07-14) and no business writing someone's profile now
    that members hold their own session.
    """
    if user.team_member_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Team members only.",
        )
    return user


def get_dwight_service(request: Request) -> DwightService:
    """Build a DwightService wired to the app-level adapters."""
    state = request.app.state
    return DwightService(
        llm=state.llm,
        session_factory=state.session_factory,
        vector_store=state.vector_store,
    )


def get_pam_service(request: Request) -> PamService:
    """Build a PamService wired to the app-level adapters.

    The summary engine rides along: summaries are Pam response templates
    (recadrage 2026-07-12), served when a question calls for one.
    """
    state = request.app.state
    return PamService(
        llm=state.llm,
        session_factory=state.session_factory,
        vector_store=state.vector_store,
        summary_service=get_summary_service(request),
        # The retrieval floor is configuration (PAM_MIN_SCORE), a tuning
        # lever like LLM_MODEL - never a constant buried in the service.
        min_score=get_settings().pam_min_score,
        # The second memory: Darryl's documentary corpus (2026-07-15).
        doc_vector_store=state.doc_vector_store,
    )


def get_mood_service(request: Request) -> MoodService:
    """Build a MoodService wired to the app-level session factory."""
    return MoodService(session_factory=request.app.state.session_factory)


def get_gdrive_ingestion_service(request: Request) -> IngestionService:
    """Build the Drive ingestion loop on top of the Dwight pipeline."""
    return IngestionService(
        source=build_ingestion_source(get_settings(), kind="gdrive"),
        dwight=get_dwight_service(request),
    )


def get_darryl_service(request: Request) -> DarrylService:
    """Build a DarrylService wired to the DOCUMENTS vector collection.

    The source connector is built per request (constructors store
    configuration only, no network): tests swap the whole service via
    app.dependency_overrides, exactly like every other seam.
    """
    state = request.app.state
    settings = get_settings()
    return DarrylService(
        source=build_document_source(settings),
        llm=state.llm,
        session_factory=state.session_factory,
        vector_store=state.doc_vector_store,
        # The routing floor is configuration (DARRYL_MIN_CONFIDENCE),
        # a tuning lever like PAM_MIN_SCORE.
        min_confidence=settings.darryl_min_confidence,
    )


def get_editing_service(request: Request) -> EditingService:
    """Build the document-editing engine on top of Darryl's archivist.

    The engine decides IF a document is filed to the corpus (the person
    exception lives there); Darryl knows HOW.
    """
    state = request.app.state
    return EditingService(
        llm=state.llm,
        session_factory=state.session_factory,
        darryl=get_darryl_service(request),
    )


def get_toby_service(request: Request) -> TobyService:
    """Build a TobyService wired to the app-level session factory."""
    return TobyService(session_factory=request.app.state.session_factory)


def get_team_service(request: Request) -> TeamService:
    """Build a TeamService wired to the app-level session factory."""
    return TeamService(session_factory=request.app.state.session_factory)


def get_summary_service(request: Request) -> SummaryService:
    """Build a SummaryService wired to the app-level adapters."""
    state = request.app.state
    return SummaryService(llm=state.llm, session_factory=state.session_factory)


def get_angela_service(request: Request) -> AngelaService:
    """Build an AngelaService on top of the summary engine."""
    return AngelaService(summary_service=get_summary_service(request))


def get_handover_service(request: Request) -> HandoverService:
    """Build a HandoverService wired to the app-level session factory."""
    return HandoverService(session_factory=request.app.state.session_factory)
