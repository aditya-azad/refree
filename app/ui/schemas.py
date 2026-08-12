from uuid import UUID

from pydantic import BaseModel, ConfigDict


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
