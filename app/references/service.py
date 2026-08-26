from uuid import UUID

from app.common.errors import DatabaseEntryNotFoundError
from app.pdf_store.service import PdfStore
from app.references.bibtex import BibTeXWriter
from app.references.citation_key import (
    CitationKeyGenerator,
    _base_citation_key,
    _first_author_last_name,
)
from app.references.duplicates import DuplicateDetector
from app.references.merge import MergeResolver
from app.references.models import Reference
from app.references.repository import ReferencesRepository
from app.references.schemas import (
    ReferenceCreate,
    ReferenceRead,
    ReferenceUpdate,
)


class ReferencesService:
    def __init__(
        self, repository: ReferencesRepository, pdf_store: PdfStore
    ) -> None:
        self._repository = repository
        self._pdf_store = pdf_store

    def get_reference(self, reference_id: UUID) -> ReferenceRead:
        reference = self._repository.get_by_id(reference_id)
        return ReferenceRead.model_validate(reference)

    def get_reference_by_citation_key(self, citation_key: str) -> ReferenceRead:
        reference = self._repository.get_by_citation_key(citation_key)
        return ReferenceRead.model_validate(reference)

    def list_references(
        self, limit: int = 100, offset: int = 0
    ) -> list[ReferenceRead]:
        references = self._repository.list_references(limit, offset)
        return [ReferenceRead.model_validate(r) for r in references]

    def list_all_references(self) -> list[ReferenceRead]:
        references = self._repository.list_all_references()
        return [ReferenceRead.model_validate(r) for r in references]

    def export_bibtex(self) -> str:
        references = self._repository.list_all_references()
        return BibTeXWriter.format_bibliography(
            ReferenceRead.model_validate(r) for r in references
        )

    def export_bibtex_for_keys(self, citation_keys: list[str]) -> str:
        unique_keys = list(dict.fromkeys(citation_keys))
        references: list[Reference] = []
        missing: list[str] = []
        for key in unique_keys:
            reference = self._repository.find_by_citation_key(key)
            if reference is None:
                missing.append(key)
            else:
                references.append(reference)
        if missing:
            raise DatabaseEntryNotFoundError(
                f"citation keys not found: {', '.join(missing)}"
            )
        return BibTeXWriter.format_bibliography(
            ReferenceRead.model_validate(r) for r in references
        )

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
            item_type=reference.item_type,
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
        existing = self._repository.get_by_id(reference_id)
        if existing.pdf_path:
            self._pdf_store.delete(existing.pdf_path)
        self._repository.delete_by_id(reference_id)

    def set_pdf_path(self, reference_id: UUID, pdf_path: str) -> ReferenceRead:
        existing = self._repository.get_by_id(reference_id)
        existing.pdf_path = pdf_path
        self._repository.update_reference(existing)
        return ReferenceRead.model_validate(existing)

    def attach_pdf(self, reference_id: UUID, pdf_bytes: bytes) -> ReferenceRead:
        if pdf_bytes[:4] != b"%PDF":
            msg = "uploaded file is not a valid PDF"
            raise ValueError(msg)
        existing = self._repository.get_by_id(reference_id)
        if existing.pdf_path:
            self._pdf_store.delete(existing.pdf_path)
        relative = self._pdf_store.store(
            PdfStore.build_filename(
                _first_author_last_name(existing.authors),
                str(existing.year) if existing.year else "",
                existing.title,
            ),
            pdf_bytes,
        )
        existing.pdf_path = str(relative)
        self._repository.update_reference(existing)
        return ReferenceRead.model_validate(existing)

    def find_duplicate_groups(self) -> list[list[ReferenceRead]]:
        references = self._repository.list_all_references()
        groups = DuplicateDetector.find_groups(references)
        return [
            [ReferenceRead.model_validate(r) for r in group] for group in groups
        ]

    def merge_references(
        self,
        reference_ids: list[UUID],
        survivor_id: UUID | None = None,
        field_choices: dict[str, UUID] | None = None,
    ) -> ReferenceRead:
        unique_ids = list(dict.fromkeys(reference_ids))
        if len(unique_ids) < 2:
            msg = "at least two distinct references are required to merge"
            raise ValueError(msg)
        members = [self._repository.get_by_id(rid) for rid in unique_ids]
        result = MergeResolver.resolve(members, survivor_id, field_choices)
        for rid in result.ids_to_delete:
            self._repository.delete_by_id(rid)
        for field, value in result.merged_fields.items():
            setattr(result.survivor, field, value)
        self._repository.update_reference(result.survivor)
        return ReferenceRead.model_validate(result.survivor)

    @staticmethod
    def compute_merge_plan(
        references: list[ReferenceRead],
    ) -> tuple[UUID, dict[str, UUID]]:
        return MergeResolver.compute_plan(references)
