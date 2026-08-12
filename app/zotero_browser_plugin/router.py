from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from app.common.errors import RepositoryError
from app.common.logging import logger
from app.zotero_browser_plugin.container import ZoteroBrowserPluginContainer
from app.zotero_browser_plugin.schemas import (
    ConnectorSaveItemsRequest,
    SaveItemsResponse,
)
from app.zotero_browser_plugin.service import ZoteroBrowserPluginService

router = APIRouter(tags=["connector"])

ZoteroBrowserPluginServiceDep = Annotated[
    ZoteroBrowserPluginService,
    Depends(ZoteroBrowserPluginContainer.zotero_browser_plugin_service),
]


@router.get("/connector/ping")
async def ping() -> dict[str, str]:
    return {"status": "ok"}


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


@router.get("/connector/getSelectedCollection")
async def get_selected_collection() -> dict[str, object]:
    return {
        "libraryID": 1,
        "collectionID": None,
        "libraryName": "refree",
        "editable": True,
    }


@router.get("/connector/hasAttachmentResolvers")
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
async def save_attachment() -> JSONResponse:
    return JSONResponse(status_code=201, content={})


@router.post("/connector/saveStandaloneAttachment")
async def save_standalone_attachment() -> JSONResponse:
    return JSONResponse(status_code=201, content={})
