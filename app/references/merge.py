from dataclasses import dataclass
from uuid import UUID

from app.references.models import Reference
from app.references.schemas import ReferenceRead

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


@dataclass
class MergeResult:
    survivor: Reference
    merged_fields: dict[str, object]
    ids_to_delete: list[UUID]


class MergeResolver:
    @staticmethod
    def resolve(
        members: list[Reference],
        survivor_id: UUID | None = None,
        field_choices: dict[str, UUID] | None = None,
    ) -> MergeResult:
        by_id: dict[UUID, Reference] = {m.id: m for m in members}
        if survivor_id is not None:
            if survivor_id not in by_id:
                msg = f"survivor {survivor_id} is not among the references to merge"
                raise ValueError(msg)
            survivor = by_id[survivor_id]
        else:
            survivor = max(members, key=MergeResolver._reference_completeness)
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
        return MergeResult(
            survivor=survivor,
            merged_fields=resolved,
            ids_to_delete=[o.id for o in others],
        )

    @staticmethod
    def compute_plan(
        references: list[ReferenceRead],
    ) -> tuple[UUID, dict[str, UUID]]:
        survivor = max(references, key=MergeResolver._reference_completeness)
        field_defaults: dict[str, UUID] = {}
        for field in _ALL_MERGE_FIELDS:
            if MergeResolver._has_value(survivor, field):
                field_defaults[field] = survivor.id
            else:
                for ref in references:
                    if MergeResolver._has_value(ref, field):
                        field_defaults[field] = ref.id
                        break
        return survivor.id, field_defaults

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
            1 for field in _MERGE_FIELDS if MergeResolver._has_value(ref, field)
        )
        if MergeResolver._has_value(ref, "authors"):
            score += 1
        return score, str(ref.id)
