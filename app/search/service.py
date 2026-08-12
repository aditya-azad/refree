from app.references.schemas import ReferenceRead
from app.references.service import ReferencesService
from app.search.schemas import SearchPage

_TITLE_WEIGHT = 3
_AUTHOR_WEIGHT = 2
_FIELD_WEIGHT = 1
_AUX_FIELDS: tuple[str, ...] = (
    "citation_key",
    "doi",
    "publication_title",
    "publisher",
    "abstract_note",
)


class SearchService:
    def __init__(self, references_service: ReferencesService) -> None:
        self._references = references_service

    def search(
        self, query: str, limit: int = 100, offset: int = 0
    ) -> SearchPage:
        tokens = [t for t in query.strip().lower().split() if t]
        references = self._references.list_all_references()
        if not tokens:
            return SearchPage(results=[], total=0)
        scored: list[tuple[int, str, ReferenceRead]] = []
        for ref in references:
            score = self._score(ref, tokens)
            if score > 0:
                scored.append((score, ref.title.lower(), ref))
        scored.sort(key=lambda item: (-item[0], item[1]))
        total = len(scored)
        page = scored[offset : offset + limit]
        return SearchPage(results=[ref for _, _, ref in page], total=total)

    @staticmethod
    def _score(ref: ReferenceRead, tokens: list[str]) -> int:
        title = ref.title.lower()
        authors = " ".join(ref.authors).lower()
        aux = " ".join(
            str(getattr(ref, field) or "") for field in _AUX_FIELDS
        ).lower()
        total = 0
        for token in tokens:
            matched = False
            if token in title:
                total += _TITLE_WEIGHT
                matched = True
            if token in authors:
                total += _AUTHOR_WEIGHT
                matched = True
            if token in aux:
                total += _FIELD_WEIGHT
                matched = True
            if not matched:
                return 0
        return total
