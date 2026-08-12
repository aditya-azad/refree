from app.references.schemas import ItemCreate
from app.references.service import ReferencesService
from app.zotero_browser_plugin.schemas import (
    ConnectorItem,
    SavedReference,
)
from app.zotero_browser_plugin.session import ConnectorSessionRegistry


class ZoteroBrowserPluginService:
    def __init__(
        self,
        references_service: ReferencesService,
        session_registry: ConnectorSessionRegistry,
    ) -> None:
        self._references_service = references_service
        self._session_registry = session_registry

    def ingest_items(
        self,
        session_id: str,
        items: list[ConnectorItem],
    ) -> list[SavedReference]:
        saved: list[SavedReference] = []
        for item in items:
            reference = self._persist_item(item)
            self._session_registry.add_reference(session_id, reference)
            saved.append(reference)
        return saved

    def attach_pdf(
        self,
        session_id: str,
        attachment_meta: object,
        pdf_bytes: bytes,
    ) -> object:
        raise NotImplementedError

    def _persist_item(self, item: ConnectorItem) -> SavedReference:
        zotero_key = item.key or ""
        item_create = ItemCreate(
            name=item.title,
            description=zotero_key,
        )
        stored = self._references_service.create_item(item_create)
        return SavedReference(
            zotero_key=zotero_key,
            reference_id=stored.id,
            bibtex="",
        )
