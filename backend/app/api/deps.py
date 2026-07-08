"""FastAPI dependencies: assemble services from the app state.

The lifespan hook (main.py) builds the shared adapters once and parks
them on app.state. Dependencies only assemble: this is what lets tests
swap any seam through app.dependency_overrides without patching.
"""

from fastapi import Request

from backend.app.adapters.ingestion.factory import build_ingestion_source
from backend.app.config import get_settings
from backend.app.services.angela_service import AngelaService
from backend.app.services.dwight_service import DwightService
from backend.app.services.handover_service import HandoverService
from backend.app.services.ingestion_service import IngestionService
from backend.app.services.mood_service import MoodService
from backend.app.services.pam_service import PamService
from backend.app.services.summary_service import SummaryService
from backend.app.services.team_service import TeamService
from backend.app.services.toby_service import TobyService


def get_dwight_service(request: Request) -> DwightService:
    """Build a DwightService wired to the app-level adapters."""
    state = request.app.state
    return DwightService(
        llm=state.llm,
        session_factory=state.session_factory,
        vector_store=state.vector_store,
    )


def get_pam_service(request: Request) -> PamService:
    """Build a PamService wired to the app-level adapters."""
    state = request.app.state
    return PamService(
        llm=state.llm,
        session_factory=state.session_factory,
        vector_store=state.vector_store,
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
