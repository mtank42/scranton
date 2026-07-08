"""Transfer to Philly endpoints: the dossier and the signable fiche.

Plain feature prefix (like /mood or /team): the spec routes the fiche
through Michael's Desk, which is not in the POC scope.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from backend.app.adapters.export.handover import HANDOVER_RENDERERS
from backend.app.api.deps import get_handover_service
from backend.app.domain.schemas import HandoverDossier
from backend.app.services.handover_service import HandoverService
from backend.app.services.mood_service import MemberNotFoundError

router = APIRouter(prefix="/handover", tags=["handover"])


def parse_include_warm(raw: str | None) -> list[int] | None:
    """Decode the disclosure selection from one comma-separated param.

    A single string param keeps 'disclose nothing' expressible on the
    wire (a repeated param could not: empty lists vanish in HTTP):
    - absent            -> None  (REVIEW state: show all warm)
    - '' or 'none'      -> []    (DISCLOSURE state: withhold everything)
    - '3,7'             -> [3, 7]
    """
    if raw is None:
        return None
    cleaned = raw.strip()
    if cleaned in ("", "none"):
        return []
    try:
        return [int(part) for part in cleaned.split(",")]
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="include_warm must be comma-separated segment ids, '' or 'none'.",
        )


@router.get("/{member_id}", response_model=HandoverDossier)
def get_dossier(
    member_id: int,
    include_warm: str | None = Query(default=None),
    service: HandoverService = Depends(get_handover_service),
) -> HandoverDossier:
    """The portable dossier (the interop contract itself).

    Without include_warm: review state, every warm observation shown so
    the manager can choose. With it: the disclosure state.
    """
    try:
        return service.dossier(member_id, include_warm=parse_include_warm(include_warm))
    except MemberNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.get("/{member_id}/export")
def export_fiche(
    member_id: int,
    format: str = Query(default="html"),
    include_warm: str | None = Query(default=None),
    service: HandoverService = Depends(get_handover_service),
) -> Response:
    """The printable, signable fiche as a download.

    Until the handover_validations table exists (data model session),
    the printed signature block IS the two-party validation.
    """
    renderer = HANDOVER_RENDERERS.get(format)
    if renderer is None:
        known = ", ".join(sorted(HANDOVER_RENDERERS))
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Unknown format {format!r} (available: {known}).",
        )
    try:
        dossier = service.dossier(
            member_id, include_warm=parse_include_warm(include_warm)
        )
    except MemberNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    file = renderer(dossier)
    return Response(
        content=file.content,
        media_type=file.media_type,
        headers={"Content-Disposition": f'attachment; filename="{file.filename}"'},
    )
