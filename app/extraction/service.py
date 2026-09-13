import hashlib
from pathlib import Path
from uuid import UUID

from app.common.errors import DatabaseEntryNotFoundError
from app.extraction.embedder import Embedder
from app.extraction.extractor import PdfTextExtractor
from app.extraction.models import PdfContent
from app.extraction.repository import ExtractionRepository
from app.extraction.schemas import (
    IndexStats,
    KeywordHit,
    PaperSearchResult,
    PdfContentRead,
    SemanticHit,
)
from app.extraction.vector_store import VectorStore
from app.references.schemas import ReferenceRead
from app.references.service import ReferencesService

_TITLE_WEIGHT = 3
_ABSTRACT_WEIGHT = 2
_CONTENTS_WEIGHT = 1
_SNIPPET_WINDOW = 80


def _hash_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _normalize(value: str) -> str:
    return " ".join(value.lower().split())


def _composite_text(
    title: str, abstract: str | None, contents: str | None
) -> str:
    parts = [title]
    if abstract:
        parts.append(abstract)
    if contents:
        parts.append(contents)
    return " ".join(parts).strip()


def _snippet(text: str, first_token: str) -> str:
    index = text.lower().find(first_token)
    if index == -1:
        return text[:_SNIPPET_WINDOW].strip()
    start = max(0, index - _SNIPPET_WINDOW // 2)
    end = min(len(text), index + _SNIPPET_WINDOW // 2)
    return text[start:end].strip()


class ExtractionService:
    def __init__(
        self,
        repository: ExtractionRepository,
        references_service: ReferencesService,
        extractor: PdfTextExtractor,
        embedder: Embedder,
        vector_store: VectorStore,
    ) -> None:
        self._repository = repository
        self._references = references_service
        self._extractor = extractor
        self._embedder = embedder
        self._vector_store = vector_store

    def get_pdf_text(self, reference_id: UUID) -> str | None:
        content = self._refresh_content(reference_id)
        return content.text if content is not None else None

    def get_pdf_text_by_citation_key(self, citation_key: str) -> str | None:
        reference = self._references.get_reference_by_citation_key(citation_key)
        return self.get_pdf_text(reference.id)

    def get_content_summary(self, reference_id: UUID) -> PdfContentRead | None:
        content = self._refresh_content(reference_id)
        if content is None:
            return None
        return PdfContentRead.model_validate(content)

    def ensure_indexed(self, reference_id: UUID) -> bool:
        reference = self._references.get_reference(reference_id)
        contents = self._refresh_text(reference)
        composite = _composite_text(
            reference.title, reference.abstract_note, contents
        )
        if not composite:
            self._vector_store.delete(reference_id)
            return False
        embedding = self._embedder.embed_one(composite)
        self._vector_store.upsert(reference_id, embedding)
        return True

    def index_pending(self, batch_size: int = 100) -> IndexStats:
        stats = IndexStats()
        watermark = self._repository.load_watermark()
        references = self._references.list_all_references()
        cursor = watermark.cursor_reference_id
        if cursor is not None:
            references = [r for r in references if r.id > cursor]
        batch = references[:batch_size]
        for reference in batch:
            stats.scanned += 1
            previous = self._repository.get_content(reference.id)
            if reference.pdf_path and (
                previous is None
                or not _content_matches(previous, reference.pdf_path)
            ):
                if previous is None:
                    stats.extracted += 1
                else:
                    stats.re_extracted += 1
            contents = self._refresh_text(reference)
            composite = _composite_text(
                reference.title, reference.abstract_note, contents
            )
            if composite:
                embedding = self._embedder.embed_one(composite)
                self._vector_store.upsert(reference.id, embedding)
                stats.embedded += 1
            else:
                self._vector_store.delete(reference.id)
            watermark.cursor_reference_id = reference.id
            self._repository.save_watermark(watermark)
        if len(batch) < batch_size:
            self._cleanup_orphans(references)
            watermark.cursor_reference_id = None
            watermark.completed_scans += 1
            self._repository.save_watermark(watermark)
            stats.completed_scans = watermark.completed_scans
        stats.cursor = watermark.cursor_reference_id
        return stats

    def semantic_search(self, query: str, limit: int = 20) -> list[SemanticHit]:
        if not query.strip():
            return []
        query_vector = self._embedder.embed_one(query)
        hits = self._vector_store.search(query_vector, limit)
        results: list[SemanticHit] = []
        for reference_id, distance in hits:
            try:
                reference = self._references.get_reference(reference_id)
            except DatabaseEntryNotFoundError:
                continue
            results.append(
                SemanticHit(
                    citation_key=reference.citation_key,
                    title=reference.title,
                    authors=list(reference.authors),
                    year=reference.year,
                    score=1.0 - distance,
                    abstract=reference.abstract_note,
                )
            )
        results.sort(key=lambda h: (-h.score, h.title.lower()))
        return results

    def keyword_search(self, query: str, limit: int = 20) -> list[KeywordHit]:
        tokens = [t for t in query.strip().lower().split() if t]
        if not tokens:
            return []
        references = self._references.list_all_references()
        content_map = {
            c.reference_id: c.text for c in self._repository.list_all_content()
        }
        scored: list[KeywordHit] = []
        for reference in references:
            contents = content_map.get(reference.id, "")
            score = self._keyword_score(reference, contents, tokens)
            if score <= 0:
                continue
            haystack = contents or reference.abstract_note or reference.title
            scored.append(
                KeywordHit(
                    citation_key=reference.citation_key,
                    title=reference.title,
                    authors=list(reference.authors),
                    year=reference.year,
                    score=score,
                    snippet=_snippet(haystack, tokens[0]),
                )
            )
        scored.sort(key=lambda h: (-h.score, h.title.lower()))
        return scored[:limit]

    def search(self, query: str, limit: int = 20) -> PaperSearchResult:
        return PaperSearchResult(
            query=query,
            semantic=self.semantic_search(query, limit),
            keyword=self.keyword_search(query, limit),
        )

    @staticmethod
    def _keyword_score(
        reference: ReferenceRead,
        contents: str,
        tokens: list[str],
    ) -> int:
        title = reference.title.lower()
        abstract = (reference.abstract_note or "").lower()
        contents_lower = contents.lower()
        total = 0
        for token in tokens:
            matched = False
            if token in title:
                total += _TITLE_WEIGHT
                matched = True
            if token in abstract:
                total += _ABSTRACT_WEIGHT
                matched = True
            if token in contents_lower:
                total += _CONTENTS_WEIGHT
                matched = True
            if not matched:
                return 0
        return total

    def _refresh_text(self, reference: ReferenceRead) -> str:
        content = self._refresh_content(reference.id, reference)
        return content.text if content is not None else ""

    def _refresh_content(
        self,
        reference_id: UUID,
        reference: ReferenceRead | None = None,
    ) -> PdfContent | None:
        if reference is None:
            reference = self._references.get_reference(reference_id)
        if not reference.pdf_path:
            self._repository.delete_content(reference_id)
            self._vector_store.delete(reference_id)
            return None
        path = Path(reference.pdf_path)
        if not path.is_file():
            self._repository.delete_content(reference_id)
            self._vector_store.delete(reference_id)
            return None
        current_hash = _hash_file(path)
        existing = self._repository.get_content(reference_id)
        if existing is not None and existing.content_hash == current_hash:
            return existing
        text = self._extractor.extract(path)
        content = PdfContent(
            reference_id=reference_id,
            content_hash=current_hash,
            text=text,
            char_count=len(text),
        )
        self._repository.upsert_content(content)
        return content

    def _cleanup_orphans(self, known: list[ReferenceRead]) -> None:
        known_ids = {ref.id for ref in known}
        all_content = self._repository.list_all_content()
        for content in all_content:
            if content.reference_id not in known_ids:
                self._repository.delete_content(content.reference_id)
                self._vector_store.delete(content.reference_id)


def _content_matches(content: PdfContent, pdf_path: str) -> bool:
    path = Path(pdf_path)
    if not path.is_file():
        return False
    return content.content_hash == _hash_file(path)
