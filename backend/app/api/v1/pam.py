"""Ask Pam endpoint: plain-language questions over the validated memory.

The route prefix uses the character KEY ('pam'), never the display name:
display names live in the character config map only.
"""

from fastapi import APIRouter, Depends

from backend.app.api.deps import get_current_user, get_pam_service
from backend.app.domain.schemas import CurrentUserOut, PamAnswer, PamQuery
from backend.app.services.pam_service import PamService

# Any logged-in user may ask Pam (the agents are omnipresent actions,
# recadrage slide 08): her answers are cold-only by invariant and the
# people questions get deterministic redirects, so a member session
# sees nothing the warm layer protects. The manager-only parts of the
# Pam overlay (archive strip, previews, save/edit) have their own
# guards on their own routers.
router = APIRouter(prefix="/pam", tags=["pam"])


@router.post("/query", response_model=PamAnswer)
def query_memory(
    payload: PamQuery,
    service: PamService = Depends(get_pam_service),
    user: CurrentUserOut = Depends(get_current_user),
) -> PamAnswer:
    """Ask the collective memory a question, get a grounded answer.

    The answer only ever draws from the returned sources; an empty
    sources list means Pam honestly had nothing relevant.
    """
    return service.query(payload.question)
