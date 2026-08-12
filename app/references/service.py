import re
from collections.abc import Iterator
from datetime import UTC, datetime
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

    def list_references(self, limit: int = 100) -> list[ReferenceRead]:
        references = self._repository.list_references(limit)
        return [ReferenceRead.model_validate(r) for r in references]

    def create_reference(self, reference: ReferenceCreate) -> ReferenceRead:
        now = datetime.now(UTC)
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
            created_at=now,
            updated_at=now,
        )
        self._repository.create_reference(model)
        return ReferenceRead.model_validate(model)

    def update_reference(
        self, reference_id: UUID, reference: ReferenceUpdate
    ) -> ReferenceRead:
        existing = self._repository.get_by_id(reference_id)
        merged = existing.model_dump()
        merged.update(reference.model_dump(exclude_unset=True))
        model = Reference(**merged)
        model.id = existing.id
        model.updated_at = datetime.now(UTC)
        self._repository.update_reference(model)
        return ReferenceRead.model_validate(model)

    def delete_reference(self, reference_id: UUID) -> None:
        self._repository.delete_by_id(reference_id)

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
