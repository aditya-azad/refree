import pytest
from collections.abc import Iterator

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.references.repository import ReferencesRepository
from app.references.schemas import ReferenceCreate
from app.references.service import ReferencesService


@pytest.fixture()
def service() -> Iterator[ReferencesService]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield ReferencesService(ReferencesRepository(session))
    engine.dispose()


def _sample(**overrides: object) -> ReferenceCreate:
    fields: dict[str, object] = {
        "title": "Deep Learning",
        "authors": ["Ian Goodfellow", "Yoshua Bengio"],
        "year": 2016,
    }
    fields.update(overrides)
    return ReferenceCreate(**fields)  # type: ignore[arg-type]


def test_find_duplicate_groups_empty_when_no_references(
    service: ReferencesService,
) -> None:
    assert service.find_duplicate_groups() == []


def test_find_duplicate_groups_no_duplicates(service: ReferencesService) -> None:
    service.create_reference(_sample(citation_key="a"))
    service.create_reference(
        _sample(title="Bayesian Reasoning", citation_key="b")
    )
    groups = service.find_duplicate_groups()
    assert groups == []


def test_find_duplicate_groups_by_doi(service: ReferencesService) -> None:
    service.create_reference(
        _sample(citation_key="a", doi="10.1000/xyz")
    )
    service.create_reference(
        _sample(citation_key="b", doi="10.1000/xyz")
    )
    groups = service.find_duplicate_groups()
    assert len(groups) == 1
    assert len(groups[0]) == 2


def test_find_duplicate_groups_by_title_and_year(
    service: ReferencesService,
) -> None:
    service.create_reference(_sample(citation_key="a"))
    service.create_reference(
        _sample(
            citation_key="b",
            authors=["Different Author"],
            doi="10.2000/abc",
        )
    )
    groups = service.find_duplicate_groups()
    assert len(groups) == 1
    assert len(groups[0]) == 2


def test_merge_references_combines_fields_and_deletes_others(
    service: ReferencesService,
) -> None:
    first = service.create_reference(
        _sample(citation_key="a", doi=None, url="https://orig.example")
    )
    second = service.create_reference(
        _sample(citation_key="b", doi="10.1000/xyz", url=None)
    )
    merged = service.merge_references([first.id, second.id])
    assert merged.doi == "10.1000/xyz"
    assert merged.url == "https://orig.example"
    remaining = service.list_references()
    assert len(remaining) == 1
    assert remaining[0].id == merged.id


def test_merge_references_unions_authors(service: ReferencesService) -> None:
    first = service.create_reference(
        _sample(citation_key="a", authors=["Ian Goodfellow"])
    )
    second = service.create_reference(
        _sample(citation_key="b", authors=["Yoshua Bengio"])
    )
    merged = service.merge_references([first.id, second.id])
    assert set(merged.authors) == {"Ian Goodfellow", "Yoshua Bengio"}


def test_merge_references_keeps_most_complete_as_survivor(
    service: ReferencesService,
) -> None:
    first = service.create_reference(
        _sample(
            citation_key="a",
            doi="10.1000/xyz",
            url="https://example.com",
            publisher="MIT Press",
        )
    )
    second = service.create_reference(
        _sample(citation_key="b", doi=None, url=None, publisher=None)
    )
    merged = service.merge_references([first.id, second.id])
    assert merged.id == first.id
    assert merged.doi == "10.1000/xyz"
    assert merged.publisher == "MIT Press"


def test_merge_references_requires_two_distinct_ids(
    service: ReferencesService,
) -> None:
    ref = service.create_reference(_sample(citation_key="a"))
    with pytest.raises(ValueError):
        service.merge_references([ref.id])
