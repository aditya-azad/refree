from app.references.schemas import ItemCreate
from app.references.service import ReferencesService
from app.zotero_browser_plugin.schemas import (
    ZoteroItemCreate,
    ZoteroItemRead,
)


class ZoteroBrowserPluginService:
    def __init__(self, references_service: ReferencesService) -> None:
        self._references_service = references_service

    def ingest_item(self, zotero_item: ZoteroItemCreate) -> ZoteroItemRead:
        item_create = ItemCreate(
            name=zotero_item.title,
            description=zotero_item.zotero_key,
        )
        stored = self._references_service.create_item(item_create)
        return ZoteroItemRead(
            zotero_key=zotero_item.zotero_key, item_id=stored.id
        )

    def sync_from_zotero(self) -> list[ZoteroItemRead]:
        return []
