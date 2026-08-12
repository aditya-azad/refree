import re
from pathlib import Path
from typing import Protocol
from uuid import UUID

from app.common.errors import DatabaseEntryNotFoundError, RepositoryError
from app.references.schemas import ReferenceCreate, ReferenceRead
from app.references.service import ReferencesService
from app.zotero_import.schemas import (
    ZoteroAttachment,
    ZoteroImportResult,
    ZoteroItem,
)

_SKIP_ITEM_TYPES = frozenset({"attachment", "note"})
_UNSAFE_FILENAME_CHARS = re.compile(r'[\\/:*?"<>|\s]+')


class ZoteroClient(Protocol):
    def list_items(self) -> list[ZoteroItem]: ...

    def citation_keys(self, item_keys: list[str]) -> dict[str, str]: ...

    def list_pdf_attachments(self) -> list[ZoteroAttachment]: ...

    def download_attachment(self, item_key: str) -> bytes: ...


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


def _first_author_last_name(item: ZoteroItem) -> str:
    for creator in item.creators:
        if creator.creator_type != "author":
            continue
        if creator.last_name:
            return creator.last_name
        if creator.name:
            return creator.name
        return ""
    return ""


def _sanitize_filename_part(value: str) -> str:
    return _UNSAFE_FILENAME_CHARS.sub("", value).strip()


def _build_pdf_filename(item: ZoteroItem) -> str:
    stem = _sanitize_filename_part(
        f"{_first_author_last_name(item)}{_extract_year(item.date)}{item.title}"
    )
    if not stem:
        stem = item.item_key
    return f"{stem}.pdf"


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
        pdf_dir: Path,
    ) -> None:
        self._client = client
        self._references_service = references_service
        self._pdf_dir = pdf_dir

    def import_all(self) -> ZoteroImportResult:
        result = ZoteroImportResult()
        items = self._client.list_items()
        keys = self._client.citation_keys([it.item_key for it in items])
        references_by_key: dict[str, ReferenceRead] = {}
        for item in items:
            if item.item_type in _SKIP_ITEM_TYPES:
                result.skipped += 1
                continue
            item.citation_key = keys.get(item.item_key)
            try:
                reference_create = _zotero_item_to_reference_create(item)
                reference, created = self._references_service.upsert_reference(
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
            references_by_key[item.item_key] = reference
            if created:
                result.imported += 1
            else:
                result.updated += 1
        self._import_pdfs(items, references_by_key, result)
        return result

    def _import_pdfs(
        self,
        items: list[ZoteroItem],
        references_by_key: dict[str, ReferenceRead],
        result: ZoteroImportResult,
    ) -> None:
        items_by_key = {it.item_key: it for it in items}
        for attachment in self._client.list_pdf_attachments():
            parent_key = attachment.parent_item_key
            reference = (
                references_by_key.get(parent_key) if parent_key else None
            )
            if reference is None or reference.pdf_path:
                result.skipped += 1
                continue
            item = items_by_key.get(parent_key or "")
            if item is None:
                result.skipped += 1
                continue
            try:
                pdf_bytes = self._client.download_attachment(
                    attachment.item_key
                )
                self._store_pdf(
                    reference.id, _build_pdf_filename(item), pdf_bytes
                )
            except (RepositoryError, OSError, RuntimeError, ValueError) as e:
                result.errors.append(f"{attachment.item_key}: {e}")
                continue
            result.pdfs_imported += 1

    def _store_pdf(
        self,
        reference_id: UUID,
        filename: str,
        pdf_bytes: bytes,
    ) -> None:
        self._pdf_dir.mkdir(parents=True, exist_ok=True)
        path = self._pdf_dir / filename
        if path.exists():
            stem, _, ext = filename.rpartition(".")
            counter = 1
            while path.exists():
                path = self._pdf_dir / f"{stem}_{counter}.{ext}"
                counter += 1
        path.write_bytes(pdf_bytes)
        relative = path.relative_to(self._pdf_dir)
        self._references_service.set_pdf_path(reference_id, str(relative))
