from collections.abc import Iterator

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.references.repository import ReferencesRepository
from app.references.schemas import ReferenceCreate
from app.references.service import ReferencesService
from app.search.schemas import SearchPage
from app.search.service import SearchService


@pytest.fixture()
def search_service() -> Iterator[SearchService]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield SearchService(ReferencesService(ReferencesRepository(session)))
    engine.dispose()


def _sample(**overrides: object) -> ReferenceCreate:
    fields: dict[str, object] = {
        "title": "Deep Learning",
        "authors": ["Ian Goodfellow", "Yoshua Bengio"],
        "year": 2016,
    }
    fields.update(overrides)
    return ReferenceCreate(**fields)  # type: ignore[arg-type]


def test_search_returns_matching_references(search_service: SearchService) -> None:
    search_service._references.create_reference(_sample())
    search_service._references.create_reference(
        _sample(title="Reinforcement Learning", authors=["Richard Sutton"])
    )
    page = search_service.search("deep", limit=100)
    assert page.total == 1
    assert page.results[0].title == "Deep Learning"


def test_search_no_matches_returns_empty(search_service: SearchService) -> None:
    search_service._references.create_reference(_sample())
    page = search_service.search("quantum")
    assert page.total == 0
    assert page.results == []


def test_search_empty_query_returns_empty(search_service: SearchService) -> None:
    search_service._references.create_reference(_sample())
    assert search_service.search("") == SearchPage(results=[], total=0)
    assert search_service.search("   ") == SearchPage(results=[], total=0)


def test_search_multi_token_requires_all_tokens(search_service: SearchService) -> None:
    search_service._references.create_reference(_sample())
    page_all = search_service.search("deep learning")
    assert page_all.total == 1
    page_partial = search_service.search("deep quantum")
    assert page_partial.total == 0


def test_search_title_outranks_field_match(search_service: SearchService) -> None:
    search_service._references.create_reference(
        _sample(title="Reinforcement Learning", citation_key="rl2020")
    )
    search_service._references.create_reference(
        _sample(title="Some Other Topic", citation_key="learning2021")
    )
    page = search_service.search("learning")
    assert page.total == 2
    assert page.results[0].title == "Reinforcement Learning"


def test_search_pagination(search_service: SearchService) -> None:
    for i in range(5):
        search_service._references.create_reference(
            _sample(title=f"Deep Learning Volume {i}")
        )
    page1 = search_service.search("deep", limit=2, offset=0)
    page2 = search_service.search("deep", limit=2, offset=2)
    assert page1.total == 5
    assert len(page1.results) == 2
    assert page2.total == 5
    assert len(page2.results) == 2
    ids1 = {r.id for r in page1.results}
    ids2 = {r.id for r in page2.results}
    assert ids1.isdisjoint(ids2)
