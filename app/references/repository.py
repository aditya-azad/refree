from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.common.errors import (
    DatabaseEntryNotFoundError,
    RepositoryError,
    UsedAsForeignKeyError,
)
from app.references.models import Item


class ReferencesRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_id(self, item_id: UUID) -> Item:
        try:
            item = self._session.get(Item, item_id)
        except Exception as e:
            raise RepositoryError("failed to retrieve item") from e
        if item is None:
            raise DatabaseEntryNotFoundError(f"item with id {item_id}")
        return item

    def list_items(self, limit: int) -> list[Item]:
        try:
            stmt = select(Item).limit(limit)
            return list(self._session.exec(stmt))
        except Exception as e:
            raise RepositoryError("failed to list items") from e

    def create_item(self, item: Item) -> None:
        try:
            self._session.add(item)
            self._session.commit()
        except Exception as e:
            self._session.rollback()
            raise RepositoryError("failed to create item") from e

    def update_item(self, item: Item) -> None:
        try:
            existing = self._session.get(Item, item.id)
            if existing is None:
                raise DatabaseEntryNotFoundError(f"item with id {item.id}")
            self._session.merge(item)
            self._session.commit()
        except DatabaseEntryNotFoundError:
            raise
        except Exception as e:
            self._session.rollback()
            raise RepositoryError("failed to update item") from e

    def delete_item_by_id(self, item_id: UUID) -> None:
        try:
            existing = self._session.get(Item, item_id)
            if existing is None:
                raise DatabaseEntryNotFoundError(f"item with id {item_id}")
            self._session.delete(existing)
            self._session.commit()
        except DatabaseEntryNotFoundError:
            raise
        except IntegrityError as e:
            self._session.rollback()
            raise UsedAsForeignKeyError(
                f"item {item_id} is referenced by another row"
            ) from e
        except Exception as e:
            self._session.rollback()
            raise RepositoryError("failed to delete item") from e
