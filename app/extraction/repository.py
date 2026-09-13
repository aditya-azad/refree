from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.common.errors import RepositoryError
from app.extraction.models import ExtractionWatermark, PdfContent

_WATERMARK_NAME = "extraction"


class ExtractionRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_content(self, reference_id: UUID) -> PdfContent | None:
        try:
            return self._session.get(PdfContent, reference_id)
        except Exception as e:
            raise RepositoryError("failed to retrieve pdf content") from e

    def list_all_content(self) -> list[PdfContent]:
        try:
            return list(self._session.exec(select(PdfContent)))
        except Exception as e:
            raise RepositoryError("failed to list pdf content") from e

    def upsert_content(self, content: PdfContent) -> None:
        try:
            existing = self._session.get(PdfContent, content.reference_id)
            if existing is None:
                self._session.add(content)
            else:
                existing.content_hash = content.content_hash
                existing.text = content.text
                existing.char_count = content.char_count
            self._session.commit()
        except Exception as e:
            self._session.rollback()
            raise RepositoryError("failed to upsert pdf content") from e

    def delete_content(self, reference_id: UUID) -> None:
        try:
            existing = self._session.get(PdfContent, reference_id)
            if existing is not None:
                self._session.delete(existing)
                self._session.commit()
        except IntegrityError as e:
            self._session.rollback()
            raise RepositoryError("failed to delete pdf content") from e
        except Exception as e:
            self._session.rollback()
            raise RepositoryError("failed to delete pdf content") from e

    def load_watermark(self) -> ExtractionWatermark:
        try:
            watermark = self._session.get(ExtractionWatermark, _WATERMARK_NAME)
            if watermark is None:
                watermark = ExtractionWatermark(name=_WATERMARK_NAME)
                self._session.add(watermark)
                self._session.commit()
                self._session.refresh(watermark)
            return watermark
        except Exception as e:
            self._session.rollback()
            raise RepositoryError("failed to load watermark") from e

    def save_watermark(self, watermark: ExtractionWatermark) -> None:
        try:
            self._session.add(watermark)
            self._session.commit()
        except Exception as e:
            self._session.rollback()
            raise RepositoryError("failed to save watermark") from e
