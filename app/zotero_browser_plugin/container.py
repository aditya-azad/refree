from that_depends import BaseContainer
from that_depends.providers import Factory

from app.references.container import ReferencesContainer
from app.zotero_browser_plugin.service import ZoteroBrowserPluginService


class ZoteroBrowserPluginContainer(BaseContainer):
    zotero_browser_plugin_service = Factory(
        ZoteroBrowserPluginService,
        references_service=ReferencesContainer.references_service.cast,
    )
