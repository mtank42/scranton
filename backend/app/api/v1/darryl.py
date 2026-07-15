"""Darryl endpoints: sync the corpus, audit it, correct a filing.

The archivist works in the shadows (owner, 2026-07-15): no view of his
own. These endpoints feed the Pam overlay strip (recent documents,
unclassified bin) and the manager's one-click corrections.
"""

from fastapi import APIRouter, Depends, HTTPException, status

from backend.app.adapters.ingestion.gdrive import MissingCredentialsError
from backend.app.api.deps import get_darryl_service
from backend.app.domain.schemas import DarrylSyncReport, DocumentClassify, DocumentOut
from backend.app.services.darryl_service import (
    DarrylService,
    DocumentNotFoundError,
    UnknownEntityError,
)

router = APIRouter(prefix="/darryl", tags=["darryl"])


@router.post("/sync", response_model=DarrylSyncReport)
def sync(service: DarrylService = Depends(get_darryl_service)) -> DarrylSyncReport:
    """Reconcile the corpus with the shared source, one full pass.

    503 when the source is not configured (OAuth material, folder id or
    local directory missing): a configuration gap, not a client mistake.
    """
    try:
        return service.sync()
    except (MissingCredentialsError, FileNotFoundError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        )


@router.get("/documents/recent", response_model=list[DocumentOut])
def recent_documents(
    limit: int = 5, service: DarrylService = Depends(get_darryl_service)
) -> list[DocumentOut]:
    """The last ingested documents: the Pam overlay archive strip."""
    return service.recent(limit=limit)


@router.get("/documents/unclassified", response_model=list[DocumentOut])
def unclassified_documents(
    service: DarrylService = Depends(get_darryl_service),
) -> list[DocumentOut]:
    """The bin: documents Darryl refused to bet on, awaiting the manager."""
    return service.unclassified()


@router.post("/documents/{document_id}/classify", response_model=DocumentOut)
def classify_document(
    document_id: int,
    payload: DocumentClassify,
    service: DarrylService = Depends(get_darryl_service),
) -> DocumentOut:
    """File one document under a client or project: the manager decides."""
    try:
        return service.classify(document_id, payload.entity_type, payload.entity_id)
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except UnknownEntityError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        )
