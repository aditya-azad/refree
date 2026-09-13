from uuid import UUID

from pydantic import BaseModel, ConfigDict


class PdfContentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    reference_id: UUID
    content_hash: str
    char_count: int


class PaperSummary(BaseModel):
    citation_key: str
    title: str
    authors: list[str]
    year: int | None
    has_pdf: bool
    abstract: str | None


class SemanticHit(BaseModel):
    citation_key: str
    title: str
    authors: list[str]
    year: int | None
    score: float
    abstract: str | None


class KeywordHit(BaseModel):
    citation_key: str
    title: str
    authors: list[str]
    year: int | None
    score: int
    snippet: str


class PaperSearchResult(BaseModel):
    query: str
    semantic: list[SemanticHit]
    keyword: list[KeywordHit]


class IndexStats(BaseModel):
    scanned: int = 0
    extracted: int = 0
    re_extracted: int = 0
    embedded: int = 0
    removed: int = 0
    completed_scans: int = 0
    cursor: UUID | None = None
