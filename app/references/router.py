from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Query

from app.common.errors import DatabaseEntryNotFoundError, RepositoryError
from app.common.logging import logger
from app.references.container import ReferencesContainer
from app.references.schemas import ItemCreate, ItemRead, ItemUpdate
from app.references.service import ReferencesService

router = APIRouter()

ReferencesServiceDep = Annotated[
    ReferencesService, Depends(ReferencesContainer.references_service)
]


@router.get("/items", response_model=list[ItemRead], tags=["items"])
async def list_items(
    service: ReferencesServiceDep,
    limit: Annotated[int, Query(ge=1)] = 100,
) -> list[ItemRead]:
    try:
        return service.list_items(limit)
    except RepositoryError as exc:
        logger.error("failed to list items: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/items/{item_id}", response_model=ItemRead, tags=["items"])
async def get_item(
    item_id: Annotated[UUID, Path(description="UUID of the item to retrieve")],
    service: ReferencesServiceDep,
) -> ItemRead:
    try:
        return service.get_item(item_id)
    except DatabaseEntryNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RepositoryError as exc:
        logger.error("failed to retrieve item: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/items", response_model=ItemRead, status_code=201, tags=["items"])
async def create_item(
    item: ItemCreate,
    service: ReferencesServiceDep,
) -> ItemRead:
    try:
        result = service.create_item(item)
    except RepositoryError as exc:
        logger.error("failed to create item: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return result


@router.put("/items/{item_id}", response_model=ItemRead, tags=["items"])
async def update_item(
    item_id: Annotated[UUID, Path(description="UUID of the item to update")],
    item: ItemUpdate,
    service: ReferencesServiceDep,
) -> ItemRead:
    try:
        result = service.update_item(item_id, item)
    except DatabaseEntryNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RepositoryError as exc:
        logger.error("failed to update item: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return result


@router.delete("/items/{item_id}", status_code=204, tags=["items"])
async def delete_item(
    item_id: Annotated[UUID, Path(description="UUID of the item to delete")],
    service: ReferencesServiceDep,
) -> None:
    try:
        service.delete_item(item_id)
    except DatabaseEntryNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RepositoryError as exc:
        logger.error("failed to delete item: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
