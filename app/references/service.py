import re
from uuid import UUID

from app.references.citation_key import (
    CitationKeyGenerator,
    _base_citation_key,
    _first_author_last_name,
)
from app.references.models import Reference
from app.references.repository import ReferencesRepository
from app.references.schemas import (
    ReferenceCreate,
    ReferenceRead,
    ReferenceUpdate,
)


def normalize_title(title: str) -> str:
    return re.sub(r"[^a-z0-9]", "", title.lower())


def _first_author_last_name_lower(authors: list[str]) -> str:
    return _first_author_last_name(authors).lower()


_MERGE_FIELDS: tuple[str, ...] = (
    "year",
    "doi",
    "url",
    "publication_title",
    "publisher",
    "volume",
    "issue",
    "pages",
    "language",
    "abstract_note",
    "pdf_path",
)


_ALL_MERGE_FIELDS: tuple[str, ...] = (
    "title",
    "authors",
    "citation_key",
    *_MERGE_FIELDS,
)


class _DSU:
    def __init__(self, n: int) -> None:
        self._parent: list[int] = list(range(n))

    def find(self, x: int) -> int:
        root = x
        while self._parent[root] != root:
            root = self._parent[root]
        while self._parent[x] != root:
            self._parent[x], x = root, self._parent[x]
        return root

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self._parent[rb] = ra


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

    def list_all_references(self) -> list[ReferenceRead]:
        references = self._repository.list_all_references()
        return [ReferenceRead.model_validate(r) for r in references]

    def count_references(self) -> int:
        return self._repository.count_references()

    def create_reference(self, reference: ReferenceCreate) -> ReferenceRead:
        if reference.citation_key is not None:
            taken = set(
                self._repository.find_citation_keys_by_prefix(
                    reference.citation_key
                )
            )
            citation_key = CitationKeyGenerator.resolve_explicit(
                reference.citation_key, taken
            )
        else:
            base = _base_citation_key(
                reference.title, list(reference.authors), reference.year
            )
            taken = set(self._repository.find_citation_keys_by_prefix(base))
            citation_key = CitationKeyGenerator.generate(
                reference.title, list(reference.authors), reference.year, taken
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
            base = _base_citation_key(
                reference.title, list(reference.authors), reference.year
            )
            taken = set(self._repository.find_citation_keys_by_prefix(base))
            key = CitationKeyGenerator.generate(
                reference.title, list(reference.authors), reference.year, taken
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

    def find_duplicate_groups(self) -> list[list[ReferenceRead]]:
        references = self._repository.list_all_references()
        if len(references) < 2:
            return []
        dsu = _DSU(len(references))
        by_key: dict[str, int] = {}
        for index, ref in enumerate(references):
            for key in self._duplicate_keys(ref):
                existing = by_key.get(key)
                if existing is None:
                    by_key[key] = index
                else:
                    dsu.union(existing, index)
        clusters: dict[int, list[Reference]] = {}
        for index, ref in enumerate(references):
            clusters.setdefault(dsu.find(index), []).append(ref)
        groups: list[list[ReferenceRead]] = []
        for members in clusters.values():
            if len(members) < 2:
                continue
            members.sort(key=lambda r: (r.title.lower(), str(r.id)))
            groups.append([ReferenceRead.model_validate(r) for r in members])
        groups.sort(key=lambda g: g[0].title.lower())
        return groups

    def merge_references(
        self,
        reference_ids: list[UUID],
        survivor_id: UUID | None = None,
        field_choices: dict[str, UUID] | None = None,
    ) -> ReferenceRead:
        unique_ids: list[UUID] = []
        seen: set[UUID] = set()
        for rid in reference_ids:
            if rid not in seen:
                seen.add(rid)
                unique_ids.append(rid)
        if len(unique_ids) < 2:
            msg = "at least two distinct references are required to merge"
            raise ValueError(msg)
        members = [self._repository.get_by_id(rid) for rid in unique_ids]
        by_id: dict[UUID, Reference] = {m.id: m for m in members}
        if survivor_id is not None:
            if survivor_id not in by_id:
                msg = f"survivor {survivor_id} is not among the references to merge"
                raise ValueError(msg)
            survivor = by_id[survivor_id]
        else:
            survivor = max(members, key=self._reference_completeness)
        others = [m for m in members if m.id != survivor.id]
        choices = field_choices or {}
        resolved: dict[str, object] = {}
        for field in _ALL_MERGE_FIELDS:
            source_id = choices.get(field)
            if source_id is not None:
                source = by_id.get(source_id)
                if source is not None:
                    resolved[field] = (
                        list(source.authors)
                        if field == "authors"
                        else getattr(source, field, None)
                    )
        for field in _MERGE_FIELDS:
            if field in choices:
                continue
            if getattr(survivor, field, None) is None:
                for other in others:
                    value = getattr(other, field, None)
                    if value is not None:
                        resolved[field] = value
                        break
        if "authors" not in choices:
            combined_authors: list[str] = list(survivor.authors)
            for other in others:
                for author in other.authors:
                    if author not in combined_authors:
                        combined_authors.append(author)
            resolved["authors"] = combined_authors
        for other in others:
            self._repository.delete_by_id(other.id)
        for field, value in resolved.items():
            setattr(survivor, field, value)
        self._repository.update_reference(survivor)
        return ReferenceRead.model_validate(survivor)

    @staticmethod
    def compute_merge_plan(
        references: list[ReferenceRead],
    ) -> tuple[UUID, dict[str, UUID]]:
        survivor = max(
            references, key=ReferencesService._reference_completeness
        )
        field_defaults: dict[str, UUID] = {}
        for field in _ALL_MERGE_FIELDS:
            if ReferencesService._has_value(survivor, field):
                field_defaults[field] = survivor.id
            else:
                for ref in references:
                    if ReferencesService._has_value(ref, field):
                        field_defaults[field] = ref.id
                        break
        return survivor.id, field_defaults

    @staticmethod
    def _duplicate_keys(ref: Reference) -> list[str]:
        keys: list[str] = []
        if ref.doi:
            keys.append("doi:" + ref.doi.lower())
        norm_title = normalize_title(ref.title)
        if norm_title:
            if ref.year is not None:
                keys.append(f"ty:{norm_title}|{ref.year}")
            author = _first_author_last_name_lower(list(ref.authors))
            if author:
                keys.append(f"ta:{norm_title}|{author}")
        return keys

    @staticmethod
    def _has_value(ref: Reference | ReferenceRead, field: str) -> bool:
        if field == "authors":
            return bool(getattr(ref, "authors", None))
        if field == "year":
            return getattr(ref, "year", None) is not None
        return bool(getattr(ref, field, None))

    @staticmethod
    def _reference_completeness(
        ref: Reference | ReferenceRead,
    ) -> tuple[int, str]:
        score = sum(
            1
            for field in _MERGE_FIELDS
            if ReferencesService._has_value(ref, field)
        )
        if ReferencesService._has_value(ref, "authors"):
            score += 1
        return score, str(ref.id)
