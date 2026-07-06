"""Smart Summaries endpoints: the catalog and the living documents.

No character prefix here: Smart Summaries is the one feature explicitly
powered by Dwight and Pam together (SCRANTON_CONTEXT section 3).
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status

from backend.app.api.deps import get_summary_service
from backend.app.domain.schemas import SummaryCatalog, SummaryResponse
from backend.app.services.summary_service import (
    SummaryProcessingError,
    SummaryService,
    TargetNotFoundError,
    TargetRequiredError,
    UnknownTemplateError,
)

router = APIRouter(prefix="/summaries", tags=["summaries"])


@router.get("", response_model=SummaryCatalog)
def get_catalog(service: SummaryService = Depends(get_summary_service)) -> SummaryCatalog:
    """The six templates and every pickable target, in one call."""
    return service.catalog()


@router.get("/{template_id}", response_model=SummaryResponse)
def generate_summary(
    template_id: str,
    target_id: int | None = Query(default=None),
    service: SummaryService = Depends(get_summary_service),
) -> SummaryResponse:
    """Build one living summary now, from the validated memory.

    GET on purpose: a summary is a read of the memory, computed fresh
    on every call and never stored.
    """
    try:
        return service.generate(template_id, target_id)
    except UnknownTemplateError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except TargetNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except TargetRequiredError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        )
    except SummaryProcessingError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
