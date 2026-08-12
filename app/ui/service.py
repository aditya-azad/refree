from pathlib import Path
from uuid import UUID

from fastapi import Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.common.errors import DatabaseEntryNotFoundError
from app.references.schemas import ReferenceRead
from app.references.service import ReferencesService
from app.ui.schemas import EXTRA_COLUMNS, PAGE_SIZE, Pagination, ReferenceView


class UIService:
    def __init__(
        self,
        references_service: ReferencesService,
        pdf_dir: Path,
        templates: Jinja2Templates,
    ) -> None:
        self._references = references_service
        self._pdf_dir = pdf_dir
        self._templates = templates

    def render_index(self, request: Request, page: int = 1) -> HTMLResponse:
        page = max(page, 1)
        offset = (page - 1) * PAGE_SIZE
        references = self._references.list_references(PAGE_SIZE, offset)
        total = self._references.count_references()
        entries = [self._to_view(ref) for ref in references]
        total_pages = (total + PAGE_SIZE - 1) // PAGE_SIZE if total else 1
        page = min(page, total_pages) if total else 1
        range_start = offset + 1 if total else 0
        range_end = min(offset + len(entries), total)
        pagination = Pagination(
            page=page,
            page_size=PAGE_SIZE,
            total=total,
            total_pages=total_pages,
            has_prev=page > 1,
            has_next=page < total_pages,
            range_start=range_start,
            range_end=range_end,
        )
        return self._templates.TemplateResponse(
            request,
            "index.html",
            {
                "entries": entries,
                "extra_columns": EXTRA_COLUMNS,
                "pagination": pagination,
            },
        )

    def render_details(
        self, request: Request, reference_id: UUID
    ) -> HTMLResponse:
        reference = self._references.get_reference(reference_id)
        view = self._to_view(reference)
        return self._templates.TemplateResponse(
            request,
            "_details.html",
            {"reference": view},
        )

    def resolve_pdf_path(self, reference_id: UUID) -> Path:
        reference = self._references.get_reference(reference_id)
        if not reference.pdf_path:
            msg = f"reference {reference_id} has no attached PDF"
            raise DatabaseEntryNotFoundError(msg)
        path = (self._pdf_dir / reference.pdf_path).resolve()
        if not path.is_file():
            msg = f"PDF file not found for reference {reference_id}"
            raise DatabaseEntryNotFoundError(msg)
        return path

    def _to_view(self, reference: ReferenceRead) -> ReferenceView:
        return ReferenceView(
            id=reference.id,
            title=reference.title,
            authors=list(reference.authors),
            year=reference.year,
            citation_key=reference.citation_key,
            doi=reference.doi,
            url=reference.url,
            publication_title=reference.publication_title,
            publisher=reference.publisher,
            volume=reference.volume,
            issue=reference.issue,
            pages=reference.pages,
            language=reference.language,
            abstract_note=reference.abstract_note,
            pdf_path=reference.pdf_path,
            has_pdf=bool(reference.pdf_path),
        )
