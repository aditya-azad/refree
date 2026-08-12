from that_depends import BaseContainer
from that_depends.providers import Factory

from app.common.container import CommonContainer
from app.references.repository import ReferencesRepository
from app.references.service import ReferencesService


class ReferencesContainer(BaseContainer):
    references_repository = Factory(
        ReferencesRepository, session=CommonContainer.session.cast
    )
    references_service = Factory(
        ReferencesService, repository=references_repository.cast
    )
