import re
from typing import Protocol

from app.common.errors import DatabaseEntryNotFoundError, RepositoryError
from app.references.schemas import ReferenceCreate
from app.references.service import ReferencesService
from app.zotero_import.schemas import ZoteroImportResult, ZoteroItem

_SKIP_ITEM_TYPES = frozenset({"attachment", "note"})


class ZoteroClient(Protocol):
    def list_items(self) -> list[ZoteroItem]: ...

    def citation_keys(self, item_keys: list[str]) -> dict[str, str]: ...


def _extract_year(date: str | None) -> str:
    if not date:
        return ""
    match = re.search(r"\d{4}", date)
    return match.group(0) if match else ""


def _zotero_authors(item: ZoteroItem) -> list[str]:
    authors: list[str] = []
    for creator in item.creators:
        if creator.creator_type != "author":
            continue
        if creator.last_name and creator.first_name:
            authors.append(f"{creator.first_name} {creator.last_name}")
        elif creator.last_name:
            authors.append(creator.last_name)
        elif creator.name:
            authors.append(creator.name)
    return authors


def _zotero_year(item: ZoteroItem) -> int | None:
    year_str = _extract_year(item.date)
    return int(year_str) if year_str else None


def _zotero_item_to_reference_create(item: ZoteroItem) -> ReferenceCreate:
    return ReferenceCreate(
        title=item.title,
        authors=_zotero_authors(item),
        year=_zotero_year(item),
        doi=item.doi,
        url=item.url,
        publication_title=item.publication_title,
        publisher=item.publisher,
        volume=item.volume,
        issue=item.issue,
        pages=item.pages,
        language=item.language,
        abstract_note=item.abstract_note,
        citation_key=item.citation_key,
    )


class ZoteroImportService:
    def __init__(
        self,
        client: ZoteroClient,
        references_service: ReferencesService,
    ) -> None:
        self._client = client
        self._references_service = references_service

    def import_all(self) -> ZoteroImportResult:
        result = ZoteroImportResult()
        items = self._client.list_items()
        keys = self._client.citation_keys([it.item_key for it in items])
        for item in items:
            if item.item_type in _SKIP_ITEM_TYPES:
                result.skipped += 1
                continue
            item.citation_key = keys.get(item.item_key)
            try:
                reference_create = _zotero_item_to_reference_create(item)
                _, created = self._references_service.upsert_reference(
                    reference_create
                )
            except (
                RepositoryError,
                DatabaseEntryNotFoundError,
                RuntimeError,
                ValueError,
            ) as e:
                result.errors.append(f"{item.item_key}: {e}")
                continue
            if created:
                result.imported += 1
            else:
                result.updated += 1
        return result
