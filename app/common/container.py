from collections.abc import Iterator

from sqlmodel import Session
from that_depends import BaseContainer
from that_depends.providers import ContextResource
from that_depends.providers.context_resources import ContextScopes

from app.common.database import engine


def _create_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session


class CommonContainer(BaseContainer):
    default_scope = ContextScopes.REQUEST
    session = ContextResource(_create_session)
