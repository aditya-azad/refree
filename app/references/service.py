import re
from collections.abc import Iterator
from uuid import UUID

from app.references.models import Reference
from app.references.repository import ReferencesRepository
from app.references.schemas import (
    ReferenceCreate,
    ReferenceRead,
    ReferenceUpdate,
)

_FILLER_WORDS = frozenset(
    {
        "a",
        "an",
        "the",
        "and",
        "or",
        "but",
        "of",
        "in",
        "on",
        "at",
        "to",
        "for",
        "with",
        "by",
        "from",
        "as",
        "is",
        "are",
        "be",
        "been",
        "this",
        "that",
        "these",
        "those",
        "it",
        "its",
        "de",
        "du",
        "la",
        "le",
        "el",
        "los",
        "las",
    }
)


def _first_author_last_name(authors: list[str]) -> str:
    if not authors:
        return ""
    parts = re.split(r"\s+", authors[0].strip())
    return parts[-1] if parts else ""


def _camel_case_word(word: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9]", "", word)
    if not cleaned:
        return ""
    return cleaned[0].upper() + cleaned[1:].lower()


def _short_title(title: str) -> str:
    picked: list[str] = []
    for word in re.split(r"\s+", title.strip()):
        if not word:
            continue
        if word.lower() in _FILLER_WORDS:
            continue
        camel = _camel_case_word(word)
        if camel:
            picked.append(camel)
        if len(picked) == 3:
            break
    return "".join(picked)


def _base_citation_key(title: str, authors: list[str], year: int | None) -> str:
    auth = re.sub(r"[^A-Za-z0-9]", "", _first_author_last_name(authors)).lower()
    if not auth:
        auth = "anon"
    short = _short_title(title)
    if not short:
        short = "Ref"
    yr = str(year) if year else ""
    return f"{auth}{short}{yr}"


def _disambiguation_suffixes() -> Iterator[str]:
    yield ""
    letters = "abcdefghijklmnopqrstuvwxyz"
    yield from letters
    for first in letters:
        for second in letters:
            yield first + second


class ReferencesService:
    def __init__(self, repository: ReferencesRepository) -> None:
        self._repository = repository

    def get_reference(self, reference_id: UUID) -> ReferenceRead:
        reference = self._repository.get_by_id(reference_id)
        return ReferenceRead.model_validate(reference)

    def list_references(
        self, limit: int = 100, offset: int = 0
    ) -> list[ReferenceRead]:
        references = self._repository.list_references(limit, offset)
        return [ReferenceRead.model_validate(r) for r in references]

    def count_references(self) -> int:
        return self._repository.count_references()

    def create_reference(self, reference: ReferenceCreate) -> ReferenceRead:
        if reference.citation_key is not None:
            citation_key = self._resolve_explicit_citation_key(
                reference.citation_key
            )
        else:
            citation_key = self._unique_citation_key(
                reference.title, list(reference.authors), reference.year
            )
        model = Reference(
            title=reference.title,
            authors=list(reference.authors),
            year=reference.year,
            citation_key=citation_key,
            doi=reference.doi,
            url=reference.url,
            publication_title=reference.publication_title,
            publisher=reference.publisher,
            volume=reference.volume,
            issue=reference.issue,
            pages=reference.pages,
            language=reference.language,
            abstract_note=reference.abstract_note,
        )
        self._repository.create_reference(model)
        return ReferenceRead.model_validate(model)

    def create_or_update_reference(
        self, reference: ReferenceCreate
    ) -> ReferenceRead:
        ref, _ = self.upsert_reference(reference)
        return ref

    def upsert_reference(
        self, reference: ReferenceCreate
    ) -> tuple[ReferenceRead, bool]:
        if reference.citation_key is not None:
            key = reference.citation_key
        else:
            key = self._unique_citation_key(
                reference.title, list(reference.authors), reference.year
            )
        existing = self._repository.find_by_citation_key(key)
        if existing is None:
            return self.create_reference(reference), True
        merged = existing.model_dump()
        merged.update(reference.model_dump(exclude_none=True))
        merged["citation_key"] = key
        model = Reference(**merged)
        model.id = existing.id
        self._repository.update_reference(model)
        return ReferenceRead.model_validate(model), False

    def update_reference(
        self, reference_id: UUID, reference: ReferenceUpdate
    ) -> ReferenceRead:
        existing = self._repository.get_by_id(reference_id)
        merged = existing.model_dump()
        merged.update(reference.model_dump(exclude_unset=True))
        model = Reference(**merged)
        model.id = existing.id
        self._repository.update_reference(model)
        return ReferenceRead.model_validate(model)

    def delete_reference(self, reference_id: UUID) -> None:
        self._repository.delete_by_id(reference_id)

    def set_pdf_path(self, reference_id: UUID, pdf_path: str) -> ReferenceRead:
        existing = self._repository.get_by_id(reference_id)
        existing.pdf_path = pdf_path
        self._repository.update_reference(existing)
        return ReferenceRead.model_validate(existing)

    def _unique_citation_key(
        self, title: str, authors: list[str], year: int | None
    ) -> str:
        base = _base_citation_key(title, authors, year)
        taken = set(self._repository.find_citation_keys_by_prefix(base))
        for suffix in _disambiguation_suffixes():
            candidate = base + suffix
            if candidate not in taken:
                return candidate
        msg = f"exhausted citation key space for base {base!r}"
        raise RuntimeError(msg)

    def _resolve_explicit_citation_key(self, key: str) -> str:
        for suffix in _disambiguation_suffixes():
            candidate = key + suffix
            if self._repository.find_by_citation_key(candidate) is None:
                return candidate
        msg = f"exhausted citation key space for key {key!r}"
        raise RuntimeError(msg)
