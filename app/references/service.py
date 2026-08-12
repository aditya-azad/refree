from datetime import UTC, datetime
from uuid import UUID

from app.references.models import Item
from app.references.repository import ReferencesRepository
from app.references.schemas import ItemCreate, ItemRead, ItemUpdate


class ReferencesService:
    def __init__(self, repository: ReferencesRepository) -> None:
        self._repository = repository

    def get_item(self, item_id: UUID) -> ItemRead:
        item = self._repository.get_by_id(item_id)
        return ItemRead.model_validate(item)

    def list_items(self, limit: int = 100) -> list[ItemRead]:
        items = self._repository.list_items(limit)
        return [ItemRead.model_validate(i) for i in items]

    def create_item(self, item: ItemCreate) -> ItemRead:
        now = datetime.now(UTC)
        model = Item(**item.model_dump(), created_at=now, updated_at=now)
        self._repository.create_item(model)
        return ItemRead.model_validate(model)

    def update_item(self, item_id: UUID, item: ItemUpdate) -> ItemRead:
        existing = self._repository.get_by_id(item_id)
        merged = existing.model_dump()
        merged.update(item.model_dump(exclude_unset=True))
        model = Item(**merged)
        model.id = existing.id
        model.updated_at = datetime.now(UTC)
        self._repository.update_item(model)
        return ItemRead.model_validate(model)

    def delete_item(self, item_id: UUID) -> None:
        self._repository.delete_item_by_id(item_id)
