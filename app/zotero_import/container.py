from pathlib import Path

import httpx
from that_depends import BaseContainer
from that_depends.providers import Factory, Singleton, State

from app.common.config import PDF_DIR
from app.references.container import ReferencesContainer
from app.zotero_import.client import ZoteroLocalClient
from app.zotero_import.service import ZoteroImportService


class ZoteroImportContainer(BaseContainer):
    zotero_base_url = State[str]()
    zotero_storage_dir = State[Path]()
    http_client = Singleton(httpx.Client, timeout=10.0)
    zotero_local_client = Singleton(
        ZoteroLocalClient,
        base_url=zotero_base_url.cast,
        http=http_client.cast,
    )
    zotero_import_service = Factory(
        ZoteroImportService,
        client=zotero_local_client.cast,
        references_service=ReferencesContainer.references_service.cast,
        pdf_dir=PDF_DIR,
        zotero_storage_dir=zotero_storage_dir.cast,
    )
