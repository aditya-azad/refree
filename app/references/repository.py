from uuid import UUID

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.common.errors import (
    DatabaseEntryNotFoundError,
    RepositoryError,
    UsedAsForeignKeyError,
)
from app.references.models import Reference


class ReferencesRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_id(self, reference_id: UUID) -> Reference:
        try:
            reference = self._session.get(Reference, reference_id)
        except Exception as e:
            raise RepositoryError("failed to retrieve reference") from e
        if reference is None:
            raise DatabaseEntryNotFoundError(
                f"reference with id {reference_id}"
            )
        return reference

    def list_references(self, limit: int, offset: int = 0) -> list[Reference]:
        try:
            stmt = (
                select(Reference)
                .order_by(Reference.title)
                .limit(limit)
                .offset(offset)
            )
            return list(self._session.exec(stmt))
        except Exception as e:
            raise RepositoryError("failed to list references") from e

    def list_all_references(self) -> list[Reference]:
        try:
            stmt = select(Reference).order_by(Reference.title)
            return list(self._session.exec(stmt))
        except Exception as e:
            raise RepositoryError("failed to list references") from e

    def count_references(self) -> int:
        try:
            stmt = select(func.count()).select_from(Reference)
            return self._session.exec(stmt).one()
        except Exception as e:
            raise RepositoryError("failed to count references") from e

    def create_reference(self, reference: Reference) -> None:
        try:
            self._session.add(reference)
            self._session.commit()
        except Exception as e:
            self._session.rollback()
            raise RepositoryError("failed to create reference") from e

    def update_reference(self, reference: Reference) -> None:
        try:
            existing = self._session.get(Reference, reference.id)
            if existing is None:
                raise DatabaseEntryNotFoundError(
                    f"reference with id {reference.id}"
                )
            self._session.merge(reference)
            self._session.commit()
        except DatabaseEntryNotFoundError:
            raise
        except Exception as e:
            self._session.rollback()
            raise RepositoryError("failed to update reference") from e

    def delete_by_id(self, reference_id: UUID) -> None:
        try:
            existing = self._session.get(Reference, reference_id)
            if existing is None:
                raise DatabaseEntryNotFoundError(
                    f"reference with id {reference_id}"
                )
            self._session.delete(existing)
            self._session.commit()
        except DatabaseEntryNotFoundError:
            raise
        except IntegrityError as e:
            self._session.rollback()
            raise UsedAsForeignKeyError(
                f"reference {reference_id} is referenced by another row"
            ) from e
        except Exception as e:
            self._session.rollback()
            raise RepositoryError("failed to delete reference") from e

    def find_citation_keys_by_prefix(self, prefix: str) -> list[str]:
        try:
            stmt = select(Reference.citation_key).where(
                Reference.citation_key.startswith(prefix)
            )
            return list(self._session.exec(stmt))
        except Exception as e:
            raise RepositoryError("failed to lookup citation keys") from e

    def find_by_citation_key(self, key: str) -> Reference | None:
        try:
            stmt = select(Reference).where(Reference.citation_key == key)
            return self._session.exec(stmt).first()
        except Exception as e:
            raise RepositoryError(
                "failed to lookup reference by citation key"
            ) from e
