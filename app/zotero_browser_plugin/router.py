from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.common.errors import RepositoryError
from app.common.logging import logger
from app.zotero_browser_plugin.container import ZoteroBrowserPluginContainer
from app.zotero_browser_plugin.schemas import ZoteroItemCreate, ZoteroItemRead
from app.zotero_browser_plugin.service import ZoteroBrowserPluginService

router = APIRouter()

ZoteroBrowserPluginServiceDep = Annotated[
    ZoteroBrowserPluginService,
    Depends(ZoteroBrowserPluginContainer.zotero_browser_plugin_service),
]


@router.post(
    "/zotero/items",
    response_model=ZoteroItemRead,
    status_code=201,
    tags=["zotero"],
)
async def ingest_item(
    zotero_item: ZoteroItemCreate,
    service: ZoteroBrowserPluginServiceDep,
) -> ZoteroItemRead:
    try:
        return service.ingest_item(zotero_item)
    except RepositoryError as exc:
        logger.error("failed to ingest zotero item: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post(
    "/zotero/sync",
    response_model=list[ZoteroItemRead],
    tags=["zotero"],
)
async def sync_from_zotero(
    service: ZoteroBrowserPluginServiceDep,
) -> list[ZoteroItemRead]:
    logger.info("sync requested from zotero")
    try:
        return service.sync_from_zotero()
    except RepositoryError as exc:
        logger.error("failed to sync from zotero: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
