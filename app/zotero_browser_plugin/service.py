import re
from pathlib import Path
from uuid import UUID

from app.references.schemas import ReferenceCreate
from app.references.service import ReferencesService
from app.zotero_browser_plugin.schemas import (
    ConnectorAttachmentMetadata,
    ConnectorItem,
    PdfAttachment,
    SavedReference,
)
from app.zotero_browser_plugin.session import ConnectorSessionRegistry

_UNSAFE_CHARS = re.compile(r'[\\/:*?"<>|\s]+')


def _sanitize_filename_part(value: str) -> str:
    return _UNSAFE_CHARS.sub("", value).strip()


def _first_author_last_name(item: ConnectorItem) -> str:
    for creator in item.creators:
        if creator.creator_type != "author":
            continue
        if creator.last_name:
            return creator.last_name
        if creator.name:
            parts = creator.name.split()
            return parts[0] if parts else ""
        return ""
    return ""


def _extract_year(date: str | None) -> str:
    if not date:
        return ""
    match = re.search(r"\d{4}", date)
    return match.group(0) if match else ""


def _connector_authors(item: ConnectorItem) -> list[str]:
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


def _connector_year(item: ConnectorItem) -> int | None:
    year_str = _extract_year(item.date)
    return int(year_str) if year_str else None


def _build_pdf_filename(last_name: str, year: str, title: str) -> str:
    stem = _sanitize_filename_part(f"{last_name}{year}{title}")
    if not stem:
        stem = "untitled"
    return f"{stem}.pdf"


class ZoteroBrowserPluginService:
    def __init__(
        self,
        references_service: ReferencesService,
        session_registry: ConnectorSessionRegistry,
        pdf_dir: Path,
    ) -> None:
        self._references_service = references_service
        self._session_registry = session_registry
        self._pdf_dir = pdf_dir

    def ingest_items(
        self,
        session_id: str,
        items: list[ConnectorItem],
    ) -> list[SavedReference]:
        saved: list[SavedReference] = []
        for item in items:
            reference = self._persist_item(item)
            self._session_registry.add_reference(
                session_id, item.item_id or "", reference, item
            )
            saved.append(reference)
        return saved

    def attach_pdf(
        self,
        session_id: str,
        attachment_meta: ConnectorAttachmentMetadata,
        pdf_bytes: bytes,
    ) -> PdfAttachment:
        parent_id = attachment_meta.parent_item_id or ""
        entry = self._session_registry.get_entry(session_id, parent_id)
        if entry is None:
            msg = (
                f"no parent reference for sessionID={session_id!r} "
                f"parentItemID={parent_id!r}"
            )
            raise ValueError(msg)
        filename = _build_pdf_filename(
            _first_author_last_name(entry.item),
            _extract_year(entry.item.date),
            entry.item.title,
        )
        return self._store_pdf(
            entry.reference.reference_id, filename, pdf_bytes
        )

    def save_standalone_pdf(
        self,
        _session_id: str,
        attachment_meta: ConnectorAttachmentMetadata,
        pdf_bytes: bytes,
    ) -> PdfAttachment:
        title = attachment_meta.title or "Untitled Attachment"
        created = self._references_service.create_reference(
            ReferenceCreate(title=title)
        )
        filename = _build_pdf_filename("", "", title)
        return self._store_pdf(created.id, filename, pdf_bytes)

    def _persist_item(self, item: ConnectorItem) -> SavedReference:
        reference_create = ReferenceCreate(
            title=item.title,
            authors=_connector_authors(item),
            year=_connector_year(item),
            doi=item.doi,
            url=item.url,
            publication_title=item.publication_title,
            publisher=item.publisher,
            volume=item.volume,
            issue=item.issue,
            pages=item.pages,
            language=item.language,
            abstract_note=item.abstract_note,
        )
        stored = self._references_service.create_reference(reference_create)
        return SavedReference(
            reference_id=stored.id,
            bibtex="",
        )

    def _store_pdf(
        self,
        reference_id: UUID,
        filename: str,
        pdf_bytes: bytes,
    ) -> PdfAttachment:
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
        return PdfAttachment(reference_id=reference_id, path=relative)
