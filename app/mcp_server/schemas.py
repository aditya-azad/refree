from pydantic import BaseModel

from app.extraction.schemas import PaperSearchResult


class BibEntry(BaseModel):
    citation_key: str
    bibtex: str


class PdfTextResult(BaseModel):
    citation_key: str
    text: str
    char_count: int


class ToolError(BaseModel):
    error: str


__all__ = [
    "BibEntry",
    "PaperSearchResult",
    "PdfTextResult",
    "ToolError",
]
