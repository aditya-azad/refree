from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.pdf_store.service import PdfStore
from app.references.repository import ReferencesRepository
from app.references.schemas import ReferenceCreate
from app.references.service import ReferencesService


@pytest.fixture()
def service(tmp_path: Path) -> Iterator[ReferencesService]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield ReferencesService(
            ReferencesRepository(session), PdfStore(tmp_path)
        )
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


def test_find_duplicate_groups_no_duplicates(
    service: ReferencesService,
) -> None:
    service.create_reference(_sample(citation_key="a"))
    service.create_reference(
        _sample(title="Bayesian Reasoning", citation_key="b")
    )
    groups = service.find_duplicate_groups()
    assert groups == []


def test_find_duplicate_groups_by_doi(service: ReferencesService) -> None:
    service.create_reference(_sample(citation_key="a", doi="10.1000/xyz"))
    service.create_reference(_sample(citation_key="b", doi="10.1000/xyz"))
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


def test_merge_references_with_survivor_id_overrides_default(
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
    merged = service.merge_references(
        [first.id, second.id], survivor_id=second.id
    )
    assert merged.id == second.id


def test_merge_references_with_field_choices_picks_specified_values(
    service: ReferencesService,
) -> None:
    first = service.create_reference(
        _sample(
            citation_key="a",
            title="Deep Learning",
            doi="10.1000/first",
            url="https://first.example",
        )
    )
    second = service.create_reference(
        _sample(
            citation_key="b",
            title="Deep Learning (2nd Edition)",
            doi="10.1000/second",
            url="https://second.example",
        )
    )
    merged = service.merge_references(
        [first.id, second.id],
        survivor_id=first.id,
        field_choices={"title": second.id, "doi": second.id},
    )
    assert merged.id == first.id
    assert merged.title == "Deep Learning (2nd Edition)"
    assert merged.doi == "10.1000/second"
    assert merged.url == "https://first.example"


def test_merge_references_field_choice_authors_replaces_not_unions(
    service: ReferencesService,
) -> None:
    first = service.create_reference(
        _sample(
            citation_key="a",
            authors=["Ian Goodfellow", "Yoshua Bengio"],
        )
    )
    second = service.create_reference(
        _sample(citation_key="b", authors=["Yann LeCun"])
    )
    merged = service.merge_references(
        [first.id, second.id],
        survivor_id=first.id,
        field_choices={"authors": second.id},
    )
    assert merged.authors == ["Yann LeCun"]


def test_merge_references_field_choice_not_in_choices_falls_back(
    service: ReferencesService,
) -> None:
    first = service.create_reference(
        _sample(citation_key="a", doi="10.1000/first", url=None)
    )
    second = service.create_reference(
        _sample(citation_key="b", doi=None, url="https://second.example")
    )
    merged = service.merge_references(
        [first.id, second.id],
        survivor_id=first.id,
        field_choices={"doi": first.id},
    )
    assert merged.doi == "10.1000/first"
    assert merged.url == "https://second.example"


def test_compute_merge_plan_picks_most_complete_as_survivor(
    service: ReferencesService,
) -> None:
    first = service.create_reference(
        _sample(citation_key="a", doi="10.1000/xyz", url="https://example.com")
    )
    second = service.create_reference(
        _sample(citation_key="b", doi=None, url=None)
    )
    refs = service.find_duplicate_groups()[0]
    survivor_id, field_defaults = service.compute_merge_plan(refs)
    assert survivor_id == first.id
    assert field_defaults["title"] == first.id
    assert field_defaults["doi"] == first.id
    assert field_defaults["url"] == first.id


def test_compute_merge_plan_defaults_field_to_first_non_empty(
    service: ReferencesService,
) -> None:
    first = service.create_reference(
        _sample(citation_key="a", doi=None, url=None)
    )
    second = service.create_reference(
        _sample(citation_key="b", doi="10.1000/xyz", url="https://example.com")
    )
    refs = service.find_duplicate_groups()[0]
    survivor_id, field_defaults = service.compute_merge_plan(refs)
    assert survivor_id == second.id
    assert field_defaults["doi"] == second.id
    assert field_defaults["url"] == second.id


def test_merge_references_survivor_not_in_ids_raises(
    service: ReferencesService,
) -> None:
    first = service.create_reference(_sample(citation_key="a"))
    second = service.create_reference(_sample(citation_key="b"))
    third = service.create_reference(_sample(citation_key="c"))
    with pytest.raises(ValueError):
        service.merge_references([first.id, second.id], survivor_id=third.id)
