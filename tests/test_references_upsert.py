import time
from collections.abc import Iterator

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.common.errors import DatabaseEntryNotFoundError
from app.references.models import Reference
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


def test_create_reference_with_explicit_citation_key_stores_verbatim(
    service: ReferencesService,
) -> None:
    ref = service.create_reference(_sample(citation_key="goodfellow2016deep"))
    assert ref.citation_key == "goodfellow2016deep"


def test_create_reference_without_citation_key_auto_generates(
    service: ReferencesService,
) -> None:
    ref = service.create_reference(_sample())
    assert ref.citation_key
    assert ref.citation_key != ""


def test_create_reference_disambiguates_explicit_key_collision(
    service: ReferencesService,
) -> None:
    first = service.create_reference(_sample(citation_key="dupKey"))
    second = service.create_reference(_sample(title="Other Work", citation_key="dupKey"))
    assert first.citation_key == "dupKey"
    assert second.citation_key == "dupKeya"


def test_create_or_update_reference_creates_when_absent(
    service: ReferencesService,
) -> None:
    ref = service.create_or_update_reference(
        _sample(citation_key="goodfellow2016deep")
    )
    assert ref.citation_key == "goodfellow2016deep"
    assert service.list_references() == [ref]


def test_create_or_update_reference_is_idempotent(
    service: ReferencesService,
) -> None:
    first = service.create_or_update_reference(
        _sample(citation_key="goodfellow2016deep")
    )
    time.sleep(0.01)
    second = service.create_or_update_reference(
        _sample(citation_key="goodfellow2016deep", title="Deep Learning (2nd ed.)")
    )
    assert len(service.list_references()) == 1
    assert second.id == first.id
    assert second.title == "Deep Learning (2nd ed.)"
    assert second.updated_at >= first.updated_at


def test_create_or_update_reference_auto_key_creates_each_time(
    service: ReferencesService,
) -> None:
    first = service.create_or_update_reference(_sample())
    second = service.create_or_update_reference(
        _sample(title="A Different Paper", authors=["Jane Doe"])
    )
    assert len(service.list_references()) == 2
    assert first.citation_key != second.citation_key


def test_create_or_update_reference_merges_non_none_fields_only(
    service: ReferencesService,
) -> None:
    service.create_or_update_reference(
        _sample(citation_key="key1", doi="10.1000/abc", url="https://orig.example")
    )
    updated = service.create_or_update_reference(
        _sample(citation_key="key1", doi="10.1000/xyz")
    )
    assert updated.doi == "10.1000/xyz"
    assert updated.url == "https://orig.example"


def test_find_by_citation_key_returns_model(service: ReferencesService) -> None:
    service.create_reference(_sample(citation_key="findable"))
    repo = service._repository  # type: ignore[attr-defined]
    found = repo.find_by_citation_key("findable")
    assert isinstance(found, Reference)
    assert found is not None
    assert found.citation_key == "findable"
    assert repo.find_by_citation_key("missing") is None


def test_get_reference_by_citation_key_returns_read(
    service: ReferencesService,
) -> None:
    created = service.create_reference(_sample(citation_key="findable"))
    fetched = service.get_reference_by_citation_key("findable")
    assert fetched.id == created.id
    assert fetched.citation_key == "findable"


def test_get_reference_by_citation_key_missing_raises(
    service: ReferencesService,
) -> None:
    with pytest.raises(DatabaseEntryNotFoundError):
        service.get_reference_by_citation_key("missing")
