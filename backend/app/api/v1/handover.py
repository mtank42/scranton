"""Transfer to Philly endpoints: the dossier, the fiche, the consent trail.

Plain feature prefix (like /mood or /team): the spec routes the fiche
through Michael's Desk, which is not in the POC scope.
"""

from collections.abc import Callable

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from backend.app.adapters.export.base import ExportFile
from backend.app.adapters.export.handover import HANDOVER_RENDERERS
from backend.app.api.deps import get_handover_service, require_manager
from backend.app.domain.schemas import (
    HandoverDossier,
    HandoverSelectionUpdate,
    HandoverSignatures,
    HandoverValidationCreate,
    HandoverValidationOut,
)
from backend.app.services.handover_service import (
    ActiveHandoverExistsError,
    HandoverNotFoundError,
    HandoverService,
    InvalidSelectionError,
    InvalidTransitionError,
)
from backend.app.services.mood_service import MemberNotFoundError

# Manager-only surface (identity session, lot 2): the guard sits on
# the router, so every route in this file inherits it.
router = APIRouter(
    prefix="/handover", tags=["handover"], dependencies=[Depends(require_manager)]
)

# The endpoint error contract of the consent trail: not-found is 404,
# a move the state machine forbids is 409, a bad selection is 422.
ERROR_STATUS = {
    MemberNotFoundError: status.HTTP_404_NOT_FOUND,
    HandoverNotFoundError: status.HTTP_404_NOT_FOUND,
    ActiveHandoverExistsError: status.HTTP_409_CONFLICT,
    InvalidTransitionError: status.HTTP_409_CONFLICT,
    InvalidSelectionError: status.HTTP_422_UNPROCESSABLE_CONTENT,
}


def run(call: Callable):
    """Run one service call, translating errors into the contract above."""
    try:
        return call()
    except tuple(ERROR_STATUS) as exc:
        raise HTTPException(status_code=ERROR_STATUS[type(exc)], detail=str(exc))


def as_download(file: ExportFile) -> Response:
    """Wrap a rendered file as an attachment response."""
    return Response(
        content=file.content,
        media_type=file.media_type,
        headers={"Content-Disposition": f'attachment; filename="{file.filename}"'},
    )


def known_format(format: str) -> str:
    """422 on a format no renderer claims."""
    if format not in HANDOVER_RENDERERS:
        known = ", ".join(sorted(HANDOVER_RENDERERS))
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Unknown format {format!r} (available: {known}).",
        )
    return format


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
    selection = parse_include_warm(include_warm)
    return run(lambda: service.dossier(member_id, include_warm=selection))


@router.get("/{member_id}/export")
def export_fiche(
    member_id: int,
    format: str = Query(default="html"),
    include_warm: str | None = Query(default=None),
    service: HandoverService = Depends(get_handover_service),
) -> Response:
    """The printable fiche as a download - unsigned, review material.

    The signed artifact lives on the consent trail (see export_signed):
    this free-form export never carries signatures.
    """
    renderer = HANDOVER_RENDERERS[known_format(format)]
    selection = parse_include_warm(include_warm)
    dossier = run(lambda: service.dossier(member_id, include_warm=selection))
    return as_download(renderer(dossier))


# --- The consent trail (handover_validations, session 2026-07-08) ---


@router.get("/{member_id}/validations", response_model=list[HandoverValidationOut])
def list_validations(
    member_id: int,
    service: HandoverService = Depends(get_handover_service),
) -> list[HandoverValidationOut]:
    """Every consent record for one member, newest first."""
    return run(lambda: service.validations(member_id))


@router.post("/{member_id}/validations", response_model=HandoverValidationOut)
def create_validation(
    member_id: int,
    body: HandoverValidationCreate,
    service: HandoverService = Depends(get_handover_service),
) -> HandoverValidationOut:
    """Open a handover (status: proposed). One open handover per member."""
    return run(
        lambda: service.create_validation(
            member_id, disclosed_warm_ids=body.disclosed_warm_ids
        )
    )


@router.put(
    "/validations/{validation_id}/selection", response_model=HandoverValidationOut
)
def update_selection(
    validation_id: int,
    body: HandoverSelectionUpdate,
    service: HandoverService = Depends(get_handover_service),
) -> HandoverValidationOut:
    """Rework the disclosure selection - only while status is proposed."""
    return run(
        lambda: service.update_selection(
            validation_id, disclosed_warm_ids=body.disclosed_warm_ids
        )
    )


@router.post(
    "/validations/{validation_id}/review", response_model=HandoverValidationOut
)
def mark_reviewed(
    validation_id: int,
    service: HandoverService = Depends(get_handover_service),
) -> HandoverValidationOut:
    """The member reviewed the selection: proposed -> employee_reviewed."""
    return run(lambda: service.mark_reviewed(validation_id))


@router.post(
    "/validations/{validation_id}/sign", response_model=HandoverValidationOut
)
def sign(
    validation_id: int,
    body: HandoverSignatures,
    service: HandoverService = Depends(get_handover_service),
) -> HandoverValidationOut:
    """Both parties sign: employee_reviewed -> both_validated.

    Freezes the fiche hash: from here the signed artifact is verifiable.
    """
    return run(
        lambda: service.sign(
            validation_id,
            manager_name=body.manager_name,
            member_name=body.member_name,
        )
    )


@router.post(
    "/validations/{validation_id}/send", response_model=HandoverValidationOut
)
def mark_sent(
    validation_id: int,
    service: HandoverService = Depends(get_handover_service),
) -> HandoverValidationOut:
    """Explicit manager action: both_validated -> sent.

    Deliberately NOT wired to the export download: a download is a
    verification, a transmission is a decision (owner, 2026-07-08).
    """
    return run(lambda: service.mark_sent(validation_id))


@router.get("/validations/{validation_id}/export")
def export_signed(
    validation_id: int,
    format: str = Query(default="md"),
    service: HandoverService = Depends(get_handover_service),
) -> Response:
    """Download the signed artifact (frozen selection, typed signatures).

    Byte-stable for md: hashing the download must reproduce fiche_sha256.
    """
    key = known_format(format)
    return as_download(run(lambda: service.signed_fiche(validation_id, format_key=key)))
