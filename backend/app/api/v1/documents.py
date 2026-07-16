"""Edited-document endpoints: the manager's clean notebook.

The engine behind them (editing_service) is surface-independent:
Michael's Desk and the Pam cards call these routes today, Oscar's
entity files will call the same ones tomorrow.
"""

from fastapi import APIRouter, Depends, HTTPException, status

from backend.app.api.deps import get_editing_service
from backend.app.domain.schemas import (
    DocumentDelta,
    DocumentRevision,
    DocumentReviseRequest,
    EditedDocumentCreate,
    EditedDocumentOut,
    EditedDocumentUpdate,
)
from backend.app.services.editing_service import (
    EditedDocumentNotFoundError,
    EditingService,
    RevisionProcessingError,
)

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("", response_model=EditedDocumentOut, status_code=status.HTTP_201_CREATED)
def create_document(
    payload: EditedDocumentCreate,
    service: EditingService = Depends(get_editing_service),
) -> EditedDocumentOut:
    """The first save: one generated document becomes the manager's own."""
    return service.create(payload)


@router.get("", response_model=list[EditedDocumentOut])
def list_documents(
    service: EditingService = Depends(get_editing_service),
) -> list[EditedDocumentOut]:
    """Every persisted document, latest edit first, news badges included."""
    return service.list_documents()


@router.get("/{document_id}", response_model=EditedDocumentOut)
def get_document(
    document_id: int,
    service: EditingService = Depends(get_editing_service),
) -> EditedDocumentOut:
    """One document, reopened exactly as saved."""
    try:
        return service.get(document_id)
    except EditedDocumentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.post("/{document_id}/save", response_model=EditedDocumentOut)
def save_document(
    document_id: int,
    payload: EditedDocumentUpdate,
    service: EditingService = Depends(get_editing_service),
) -> EditedDocumentOut:
    """A re-edit, manual or an accepted Dwight proposal: the new last state."""
    try:
        return service.save(document_id, payload)
    except EditedDocumentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.get("/{document_id}/delta", response_model=DocumentDelta)
def document_delta(
    document_id: int,
    service: EditingService = Depends(get_editing_service),
) -> DocumentDelta:
    """What moved since the manager last looked: the proposals to triage."""
    try:
        return service.delta(document_id)
    except EditedDocumentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.post("/{document_id}/mark-reviewed", response_model=EditedDocumentOut)
def mark_reviewed(
    document_id: int,
    service: EditingService = Depends(get_editing_service),
) -> EditedDocumentOut:
    """Advance the bookmark: the news was triaged, stop presenting it."""
    try:
        return service.mark_reviewed(document_id)
    except EditedDocumentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.post("/{document_id}/revise", response_model=DocumentRevision)
def revise_document(
    document_id: int,
    payload: DocumentReviseRequest,
    service: EditingService = Depends(get_editing_service),
) -> DocumentRevision:
    """Dwight's revision PROPOSAL with its computed diff - nothing saved."""
    try:
        return service.revise(
            document_id, payload.instruction, payload.include_segment_ids
        )
    except EditedDocumentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except RevisionProcessingError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
