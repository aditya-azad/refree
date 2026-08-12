from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse

from app.common.errors import DatabaseEntryNotFoundError, RepositoryError
from app.common.logging import logger
from app.ui.container import UIContainer
from app.ui.service import UIService

router = APIRouter(tags=["ui"])

UIServiceDep = Annotated[UIService, Depends(UIContainer.ui_service)]


@router.get("/", response_class=HTMLResponse)
async def index(request: Request, service: UIServiceDep) -> HTMLResponse:
    try:
        return service.render_index(request)
    except RepositoryError as exc:
        logger.error("failed to render index: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/ui/reference/{reference_id}", response_class=HTMLResponse)
async def reference_details(
    request: Request,
    reference_id: UUID,
    service: UIServiceDep,
) -> HTMLResponse:
    try:
        return service.render_details(request, reference_id)
    except DatabaseEntryNotFoundError as exc:
        logger.warning("reference not found: %s", exc)
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RepositoryError as exc:
        logger.error("failed to render reference %s: %s", reference_id, exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/ui/reference/{reference_id}/pdf")
async def reference_pdf(
    reference_id: UUID,
    service: UIServiceDep,
) -> FileResponse:
    try:
        path = service.resolve_pdf_path(reference_id)
    except DatabaseEntryNotFoundError as exc:
        logger.warning("pdf unavailable for %s: %s", reference_id, exc)
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RepositoryError as exc:
        logger.error("failed to resolve pdf for %s: %s", reference_id, exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return FileResponse(
        path,
        media_type="application/pdf",
        filename=path.name,
        content_disposition_type="inline",
    )
