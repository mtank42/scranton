"""Send Angela endpoint: download a summary as a file.

The route prefix uses the character KEY ('angela'); her display name
lives in the character config map only.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from backend.app.api.deps import get_angela_service, require_manager
from backend.app.services.angela_service import AngelaService, UnknownFormatError
from backend.app.services.summary_service import (
    SummaryProcessingError,
    TargetNotFoundError,
    TargetRequiredError,
    UnknownTemplateError,
)

# Manager-only surface (identity session, lot 2): the guard sits on
# the router, so every route in this file inherits it.
router = APIRouter(
    prefix="/angela", tags=["angela"], dependencies=[Depends(require_manager)]
)


@router.get("/export/{template_id}")
def export_summary(
    template_id: str,
    target_id: int | None = Query(default=None),
    format: str = Query(default="md"),
    service: AngelaService = Depends(get_angela_service),
) -> Response:
    """Assemble the summary now and deliver it as a download.

    GET on purpose: exports are reads, and a plain link in the UI (or a
    curl) is the whole client Angela needs.
    """
    try:
        file = service.export(template_id, target_id, format)
    except UnknownFormatError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        )
    except (UnknownTemplateError, TargetNotFoundError) as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except TargetRequiredError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        )
    except SummaryProcessingError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    return Response(
        content=file.content,
        media_type=file.media_type,
        headers={"Content-Disposition": f'attachment; filename="{file.filename}"'},
    )
