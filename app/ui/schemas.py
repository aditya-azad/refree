from uuid import UUID

from pydantic import BaseModel

from app.references.schemas import ReferenceRead

PAGE_SIZE: int = 100


class DuplicateGroupView(BaseModel):
    references: list[ReferenceRead]
    survivor_id: UUID
    field_defaults: dict[str, UUID]


class Pagination(BaseModel):
    page: int
    page_size: int
    total: int
    total_pages: int
    has_prev: bool
    has_next: bool
    range_start: int
    range_end: int


EXTRA_COLUMNS: tuple[tuple[str, str], ...] = (
    ("publication_title", "Publication"),
    ("publisher", "Publisher"),
    ("volume", "Volume"),
    ("issue", "Issue"),
    ("pages", "Pages"),
    ("language", "Language"),
    ("citation_key", "Citation Key"),
    ("doi", "DOI"),
    ("url", "URL"),
    ("abstract_note", "Abstract"),
    ("has_pdf", "PDF"),
)


MERGE_FIELDS: tuple[tuple[str, str], ...] = (
    ("title", "Title"),
    ("citation_key", "Citation Key"),
    ("authors", "Authors"),
    ("year", "Year"),
    ("doi", "DOI"),
    ("url", "URL"),
    ("publication_title", "Publication"),
    ("publisher", "Publisher"),
    ("volume", "Volume"),
    ("issue", "Issue"),
    ("pages", "Pages"),
    ("language", "Language"),
    ("abstract_note", "Abstract"),
    ("pdf_path", "PDF"),
)
