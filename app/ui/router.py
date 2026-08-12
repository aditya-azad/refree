from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse

from app.common.errors import DatabaseEntryNotFoundError, RepositoryError
from app.common.logging import logger
from app.ui.container import UIContainer
from app.ui.service import UIService

router = APIRouter(tags=["ui"])

UIServiceDep = Annotated[UIService, Depends(UIContainer.ui_service)]


@router.get("/", response_class=HTMLResponse)
async def index(
    request: Request,
    service: UIServiceDep,
    page: Annotated[int, Query(ge=1)] = 1,
) -> HTMLResponse:
    try:
        return service.render_index(request, page)
    except RepositoryError as exc:
        logger.error("failed to render index: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/ui/duplicates", response_class=HTMLResponse)
async def duplicates(
    request: Request,
    service: UIServiceDep,
) -> HTMLResponse:
    try:
        return service.render_duplicates(request)
    except RepositoryError as exc:
        logger.error("failed to render duplicates: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/ui/duplicates/merge")
async def merge_duplicates(
    request: Request,
    service: UIServiceDep,
) -> RedirectResponse:
    form = await request.form()
    reference_ids = [UUID(str(v)) for v in form.getlist("reference_ids")]
    survivor_id = (
        UUID(str(form["survivor_id"])) if "survivor_id" in form else None
    )
    field_choices: dict[str, UUID] = {}
    for key, value in form.multi_items():
        if key.startswith("field_"):
            field_choices[key.removeprefix("field_")] = UUID(str(value))
    try:
        service.merge_duplicates(reference_ids, survivor_id, field_choices)
    except DatabaseEntryNotFoundError as exc:
        logger.warning("merge target not found: %s", exc)
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        logger.warning("invalid merge request: %s", exc)
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RepositoryError as exc:
        logger.error("failed to merge duplicates: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return RedirectResponse(url="/ui/duplicates", status_code=303)


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
