from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Query

from app.common.errors import DatabaseEntryNotFoundError, RepositoryError
from app.common.logging import logger
from app.references.container import ReferencesContainer
from app.references.schemas import (
    DuplicateGroupRead,
    MergeRequest,
    ReferenceCreate,
    ReferenceRead,
    ReferenceUpdate,
)
from app.references.service import ReferencesService

router = APIRouter()

ReferencesServiceDep = Annotated[
    ReferencesService, Depends(ReferencesContainer.references_service)
]


@router.get(
    "/references", response_model=list[ReferenceRead], tags=["references"]
)
async def list_references(
    service: ReferencesServiceDep,
    limit: Annotated[int, Query(ge=1)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[ReferenceRead]:
    try:
        return service.list_references(limit, offset)
    except RepositoryError as exc:
        logger.error("failed to list references: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get(
    "/references/duplicates",
    response_model=list[DuplicateGroupRead],
    tags=["references"],
)
async def list_duplicates(
    service: ReferencesServiceDep,
) -> list[DuplicateGroupRead]:
    try:
        groups = service.find_duplicate_groups()
    except RepositoryError as exc:
        logger.error("failed to find duplicates: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return [DuplicateGroupRead(references=g) for g in groups]


@router.post(
    "/references/merge",
    response_model=ReferenceRead,
    tags=["references"],
)
async def merge_references(
    payload: MergeRequest,
    service: ReferencesServiceDep,
) -> ReferenceRead:
    try:
        return service.merge_references(
            payload.reference_ids,
            payload.survivor_id,
            payload.field_choices,
        )
    except DatabaseEntryNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        logger.warning("invalid merge request: %s", exc)
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RepositoryError as exc:
        logger.error("failed to merge references: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get(
    "/references/{reference_id}",
    response_model=ReferenceRead,
    tags=["references"],
)
async def get_reference(
    reference_id: Annotated[
        UUID, Path(description="UUID of the reference to retrieve")
    ],
    service: ReferencesServiceDep,
) -> ReferenceRead:
    try:
        return service.get_reference(reference_id)
    except DatabaseEntryNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RepositoryError as exc:
        logger.error("failed to retrieve reference: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post(
    "/references",
    response_model=ReferenceRead,
    status_code=201,
    tags=["references"],
)
async def create_reference(
    reference: ReferenceCreate,
    service: ReferencesServiceDep,
) -> ReferenceRead:
    try:
        result = service.create_reference(reference)
    except RepositoryError as exc:
        logger.error("failed to create reference: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return result


@router.put(
    "/references/{reference_id}",
    response_model=ReferenceRead,
    tags=["references"],
)
async def update_reference(
    reference_id: Annotated[
        UUID, Path(description="UUID of the reference to update")
    ],
    reference: ReferenceUpdate,
    service: ReferencesServiceDep,
) -> ReferenceRead:
    try:
        result = service.update_reference(reference_id, reference)
    except DatabaseEntryNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RepositoryError as exc:
        logger.error("failed to update reference: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return result


@router.delete(
    "/references/{reference_id}", status_code=204, tags=["references"]
)
async def delete_reference(
    reference_id: Annotated[
        UUID, Path(description="UUID of the reference to delete")
    ],
    service: ReferencesServiceDep,
) -> None:
    try:
        service.delete_reference(reference_id)
    except DatabaseEntryNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RepositoryError as exc:
        logger.error("failed to delete reference: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
