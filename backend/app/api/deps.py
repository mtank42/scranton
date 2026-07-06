"""FastAPI dependencies: assemble services from the app state.

The lifespan hook (main.py) builds the shared adapters once and parks
them on app.state. Dependencies only assemble: this is what lets tests
swap any seam through app.dependency_overrides without patching.
"""

from fastapi import Request

from backend.app.services.dwight_service import DwightService
from backend.app.services.pam_service import PamService


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
