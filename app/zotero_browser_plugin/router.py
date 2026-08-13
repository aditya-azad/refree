import json
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from app.common.errors import RepositoryError
from app.common.logging import logger
from app.zotero_browser_plugin.container import ZoteroBrowserPluginContainer
from app.zotero_browser_plugin.schemas import (
    ConnectorAttachmentMetadata,
    ConnectorSaveItemsRequest,
    SaveItemsResponse,
)
from app.zotero_browser_plugin.service import ZoteroBrowserPluginService

router = APIRouter(tags=["connector"])

ZoteroBrowserPluginServiceDep = Annotated[
    ZoteroBrowserPluginService,
    Depends(ZoteroBrowserPluginContainer.zotero_browser_plugin_service),
]


@router.api_route("/connector/ping", methods=["GET", "POST"])
async def ping() -> dict[str, object]:
    return {
        "prefs": {
            "automaticSnapshots": False,
            "downloadAssociatedFiles": True,
            "supportsAttachmentUpload": True,
            "supportsTagsAutocomplete": True,
        },
    }


@router.post(
    "/connector/saveItems", response_model=SaveItemsResponse, status_code=201
)
async def save_items(
    request: Request,
    service: ZoteroBrowserPluginServiceDep,
) -> SaveItemsResponse:
    body = await request.json()
    parsed = ConnectorSaveItemsRequest.model_validate(body)
    logger.info(
        "saveItems: session=%s items=%d", parsed.session_id, len(parsed.items)
    )
    try:
        service.ingest_items(parsed.session_id, parsed.items)
    except RepositoryError as exc:
        logger.error("failed to ingest connector items: %s", exc)
        raise
    return SaveItemsResponse(items=parsed.items)


@router.api_route("/connector/getSelectedCollection", methods=["GET", "POST"])
async def get_selected_collection() -> dict[str, object]:
    return {
        "libraryID": 1,
        "libraryName": "refree",
        "libraryEditable": True,
        "filesEditable": True,
        "editable": True,
        "id": None,
        "name": "refree",
        "targets": [
            {"id": "L1", "name": "refree", "filesEditable": True, "level": 0}
        ],
        "tags": {},
    }


@router.api_route("/connector/hasAttachmentResolvers", methods=["GET", "POST"])
async def has_attachment_resolvers() -> dict[str, bool]:
    return {"value": False}


@router.post("/connector/updateSession")
async def update_session() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/connector/delaySync")
async def delay_sync() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/connector/saveSnapshot")
async def save_snapshot() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/connector/saveSingleFile")
async def save_single_file() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/connector/saveAttachment")
async def save_attachment(
    request: Request,
    service: ZoteroBrowserPluginServiceDep,
) -> JSONResponse:
    session_id = request.query_params.get("sessionID", "")
    meta = _parse_attachment_metadata(request)
    pdf_bytes = await request.body()
    logger.info(
        "saveAttachment: session=%s parent=%s bytes=%d",
        session_id,
        meta.parent_item_id,
        len(pdf_bytes),
    )
    try:
        service.attach_pdf(session_id, meta, pdf_bytes)
    except (RepositoryError, ValueError) as exc:
        logger.error("failed to attach connector PDF: %s", exc)
        raise
    return JSONResponse(status_code=201, content={})


@router.post("/connector/saveStandaloneAttachment")
async def save_standalone_attachment(
    request: Request,
    service: ZoteroBrowserPluginServiceDep,
) -> JSONResponse:
    session_id = request.query_params.get("sessionID", "")
    meta = _parse_attachment_metadata(request)
    pdf_bytes = await request.body()
    logger.info(
        "saveStandaloneAttachment: session=%s bytes=%d",
        session_id,
        len(pdf_bytes),
    )
    try:
        service.save_standalone_pdf(session_id, meta, pdf_bytes)
    except (RepositoryError, ValueError) as exc:
        logger.error("failed to save standalone PDF: %s", exc)
        raise
    return JSONResponse(status_code=201, content={})


def _parse_attachment_metadata(request: Request) -> ConnectorAttachmentMetadata:
    raw = request.headers.get("X-Metadata", "{}")
    return ConnectorAttachmentMetadata.model_validate(json.loads(raw))
