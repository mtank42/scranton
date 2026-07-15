"""FastAPI dependencies: assemble services from the app state.

The lifespan hook (main.py) builds the shared adapters once and parks
them on app.state. Dependencies only assemble: this is what lets tests
swap any seam through app.dependency_overrides without patching.
"""

from fastapi import Request

from backend.app.adapters.documents.factory import build_document_source
from backend.app.adapters.ingestion.factory import build_ingestion_source
from backend.app.config import get_settings
from backend.app.services.angela_service import AngelaService
from backend.app.services.darryl_service import DarrylService
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
