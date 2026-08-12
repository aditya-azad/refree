import re

from app.pdf_store.service import PdfStore
from app.references.schemas import ReferenceCreate
from app.references.service import ReferencesService
from app.zotero_browser_plugin.schemas import (
    ConnectorAttachmentMetadata,
    ConnectorItem,
    PdfAttachment,
    SavedReference,
)
from app.zotero_browser_plugin.session import ConnectorSessionRegistry


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


def _connector_item_to_reference_create(item: ConnectorItem) -> ReferenceCreate:
    return ReferenceCreate(
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


class ZoteroBrowserPluginService:
    def __init__(
        self,
        references_service: ReferencesService,
        session_registry: ConnectorSessionRegistry,
        pdf_store: PdfStore,
    ) -> None:
        self._references_service = references_service
        self._session_registry = session_registry
        self._pdf_store = pdf_store

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
        filename = PdfStore.build_filename(
            _first_author_last_name(entry.item),
            _extract_year(entry.item.date),
            entry.item.title,
        )
        relative = self._pdf_store.store(filename, pdf_bytes)
        self._references_service.set_pdf_path(
            entry.reference.reference_id, str(relative)
        )
        return PdfAttachment(
            reference_id=entry.reference.reference_id, path=relative
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
        filename = PdfStore.build_filename("", "", title)
        relative = self._pdf_store.store(filename, pdf_bytes)
        self._references_service.set_pdf_path(created.id, str(relative))
        return PdfAttachment(reference_id=created.id, path=relative)

    def _persist_item(self, item: ConnectorItem) -> SavedReference:
        reference_create = _connector_item_to_reference_create(item)
        stored = self._references_service.create_reference(reference_create)
        return SavedReference(reference_id=stored.id)
