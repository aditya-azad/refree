import re
from pathlib import Path
from typing import Protocol

from app.common.errors import DatabaseEntryNotFoundError, RepositoryError
from app.pdf_store.service import PdfStore
from app.references.schemas import ReferenceRead
from app.references.service import ReferencesService
from app.zotero.service import (
    extract_year,
    first_author_last_name,
    to_reference_create,
)
from app.zotero_import.schemas import (
    ZoteroAttachment,
    ZoteroImportResult,
    ZoteroItem,
)

_SKIP_ITEM_TYPES = frozenset({"attachment", "note"})
_DEDUP_SUFFIX = re.compile(r" \d+(\.\w+)?$")


class ZoteroClient(Protocol):
    def list_items(self) -> list[ZoteroItem]: ...

    def citation_keys(self, item_keys: list[str]) -> dict[str, str]: ...

    def list_pdf_attachments(self) -> list[ZoteroAttachment]: ...


class ZoteroImportService:
    def __init__(
        self,
        client: ZoteroClient,
        references_service: ReferencesService,
        pdf_store: PdfStore,
        zotero_storage_dir: Path,
    ) -> None:
        self._client = client
        self._references_service = references_service
        self._pdf_store = pdf_store
        self._zotero_storage_dir = zotero_storage_dir

    def import_all(self) -> ZoteroImportResult:
        result = ZoteroImportResult()
        items = self._client.list_items()
        keys = self._client.citation_keys([it.item_key for it in items])
        references_by_key: dict[str, ReferenceRead] = {}
        for item in items:
            if item.item_type in _SKIP_ITEM_TYPES:
                continue
            item.citation_key = keys.get(item.item_key)
            try:
                reference_create = to_reference_create(item)
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
                result.pdfs_skipped += 1
                continue
            item = items_by_key.get(parent_key or "")
            if item is None:
                result.pdfs_skipped += 1
                continue
            source = self._resolve_attachment_path(attachment)
            if source is None:
                result.pdfs_skipped += 1
                continue
            try:
                pdf_bytes = source.read_bytes()
                relative = self._pdf_store.store(
                    PdfStore.build_filename(
                        first_author_last_name(item),
                        extract_year(item.date),
                        item.title,
                    ),
                    pdf_bytes,
                )
                self._references_service.set_pdf_path(
                    reference.id, str(relative)
                )
            except (RepositoryError, OSError, ValueError) as e:
                result.errors.append(f"{attachment.item_key}: {e}")
                continue
            result.pdfs_imported += 1

    def _resolve_attachment_path(
        self, attachment: ZoteroAttachment
    ) -> Path | None:
        if attachment.path is None:
            return self._find_stored_pdf(attachment.item_key)
        if attachment.path.startswith("storage:"):
            filename = attachment.path.removeprefix("storage:")
            return self._zotero_storage_dir / attachment.item_key / filename
        resolved = Path(attachment.path)
        if not resolved.is_absolute():
            return None
        if resolved.exists():
            return resolved
        stripped = _DEDUP_SUFFIX.sub(r"\1", attachment.path)
        if stripped != attachment.path:
            candidate = Path(stripped)
            if candidate.exists():
                return candidate
        return resolved

    def _find_stored_pdf(self, item_key: str) -> Path | None:
        directory = self._zotero_storage_dir / item_key
        if not directory.is_dir():
            return None
        pdfs = sorted(directory.glob("*.pdf"))
        if not pdfs:
            return None
        return pdfs[0]
