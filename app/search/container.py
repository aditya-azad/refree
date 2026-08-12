from that_depends import BaseContainer
from that_depends.providers import Factory

from app.references.container import ReferencesContainer
from app.search.service import SearchService


class SearchContainer(BaseContainer):
    search_service = Factory(
        SearchService,
        references_service=ReferencesContainer.references_service.cast,
    )
