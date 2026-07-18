"""Ingestion endpoint: pull a configured Google Drive folder.

Every pulled document runs the normal Tell Dwight pipeline: proposed
segments await validation like any hand-typed note.
"""

from fastapi import APIRouter, Depends, HTTPException, status

from backend.app.adapters.ingestion.gdrive import MissingCredentialsError
from backend.app.api.deps import get_gdrive_ingestion_service, require_manager
from backend.app.domain.schemas import IngestSummary
from backend.app.services.ingestion_service import IngestionService

# Manager-only surface (identity session, lot 2): the guard sits on
# the router, so every route in this file inherits it.
router = APIRouter(
    prefix="/ingest", tags=["ingest"], dependencies=[Depends(require_manager)]
)


@router.post("/gdrive", response_model=IngestSummary)
def ingest_gdrive(
    service: IngestionService = Depends(get_gdrive_ingestion_service),
) -> IngestSummary:
    """Pull the configured Drive folder through the capture pipeline.

    503 with a pointer to the setup doc when OAuth material or the
    folder id is missing: a configuration gap, not a client mistake.
    """
    try:
        return service.run()
    except MissingCredentialsError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        )
