"""Liveness endpoint: the first route of the /api/v1 surface."""

from fastapi import APIRouter

from backend.app.domain.schemas import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def get_health() -> HealthResponse:
    """Confirm the API process is up.

    No dependency (database, provider) is checked here on purpose: a
    liveness probe must stay cheap and must never cascade failures.
    """
    return HealthResponse(status="ok")
