"""Meet Toby endpoint: the aggregated team health view (manager-only).

Manager-only is structural in the POC (single user, no auth): the seam
for real access control is V2 multi-user.
"""

from fastapi import APIRouter, Depends, Query

from backend.app.api.deps import get_toby_service
from backend.app.domain.schemas import TobyOverview
from backend.app.services.toby_service import TobyService

router = APIRouter(prefix="/toby", tags=["toby"])


@router.get("/overview", response_model=TobyOverview)
def get_overview(
    days: int = Query(default=30, ge=1, le=365),
    service: TobyService = Depends(get_toby_service),
) -> TobyOverview:
    """Mood trends per member and team, plus weak signals, over the window."""
    return service.overview(days=days)
