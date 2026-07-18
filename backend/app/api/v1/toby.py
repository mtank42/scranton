"""Meet Toby endpoint: the aggregated team health view (manager-only).

Manager-only is enforced server-side since the identity session
(2026-07-18): the warm layer never reaches a member session.
"""

from fastapi import APIRouter, Depends, Query

from backend.app.api.deps import get_toby_service, require_manager
from backend.app.domain.schemas import TobyOverview
from backend.app.services.toby_service import TobyService

# Manager-only surface (identity session, lot 2): the guard sits on
# the router, so every route in this file inherits it.
router = APIRouter(
    prefix="/toby", tags=["toby"], dependencies=[Depends(require_manager)]
)


@router.get("/overview", response_model=TobyOverview)
def get_overview(
    days: int = Query(default=30, ge=1, le=365),
    service: TobyService = Depends(get_toby_service),
) -> TobyOverview:
    """Mood trends per member and team, plus weak signals, over the window."""
    return service.overview(days=days)
