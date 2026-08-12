from uuid import UUID

from pydantic import BaseModel, ConfigDict

PAGE_SIZE: int = 100


class ReferenceView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    authors: list[str]
    year: int | None
    citation_key: str
    doi: str | None
    url: str | None
    publication_title: str | None
    publisher: str | None
    volume: str | None
    issue: str | None
    pages: str | None
    language: str | None
    abstract_note: str | None
    pdf_path: str | None
    has_pdf: bool


class DuplicateGroupView(BaseModel):
    references: list[ReferenceView]
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
