from that_depends import BaseContainer
from that_depends.providers import Factory, Singleton

from app.common.config import PDF_DIR
from app.references.container import ReferencesContainer
from app.zotero_browser_plugin.service import ZoteroBrowserPluginService
from app.zotero_browser_plugin.session import ConnectorSessionRegistry


class ZoteroBrowserPluginContainer(BaseContainer):
    connector_session_registry = Singleton(ConnectorSessionRegistry)
    zotero_browser_plugin_service = Factory(
        ZoteroBrowserPluginService,
        references_service=ReferencesContainer.references_service.cast,
        session_registry=connector_session_registry.cast,
        pdf_dir=PDF_DIR,
    )
