from collections.abc import Iterator
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.common.config import PDF_DIR
from app.main import app
from app.pdf_store.service import PdfStore
from app.references.container import ReferencesContainer
from app.references.repository import ReferencesRepository
from app.references.schemas import ReferenceCreate
from app.references.service import ReferencesService
from app.search.container import SearchContainer
from app.search.service import SearchService


@pytest.fixture()
def client(tmp_path: Path) -> Iterator[TestClient]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    session = Session(engine)
    ref_service = ReferencesService(
        ReferencesRepository(session), PdfStore(tmp_path)
    )
    search_svc = SearchService(ref_service)
    ReferencesContainer.references_service.override_sync(ref_service)
    SearchContainer.search_service.override_sync(search_svc)
    yield TestClient(app)
    ReferencesContainer.references_service.reset_override_sync()
    SearchContainer.search_service.reset_override_sync()
    session.close()
    engine.dispose()


def _sample(**overrides: object) -> ReferenceCreate:
    fields: dict[str, object] = {
        "title": "Deep Learning",
        "authors": ["Ian Goodfellow", "Yoshua Bengio"],
        "year": 2016,
    }
    fields.update(overrides)
    return ReferenceCreate(**fields)  # type: ignore[arg-type]


def test_heartbeat(client: TestClient) -> None:
    resp = client.get("/heartbeat")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_search_returns_json_page(client: TestClient) -> None:
    ref_service = ReferencesContainer.references_service.resolve_sync()
    ref_service.create_reference(_sample(citation_key="goodfellow2016deep"))
    ref_service.create_reference(
        _sample(title="Reinforcement Learning", citation_key="sutton2018rl")
    )
    resp = client.get("/references/search?q=learning&limit=10")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    assert all("id" in r for r in body["results"])


def test_search_empty_query_returns_422(client: TestClient) -> None:
    resp = client.get("/references/search?q=")
    assert resp.status_code == 422


def test_search_route_not_shadowed_by_uuid_route(client: TestClient) -> None:
    ref_service = ReferencesContainer.references_service.resolve_sync()
    ref_service.create_reference(_sample(citation_key="goodfellow2016deep"))
    resp = client.get("/references/search?q=deep")
    assert resp.status_code == 200
    assert resp.json()["total"] == 1


def test_by_citation_key_returns_reference(client: TestClient) -> None:
    ref_service = ReferencesContainer.references_service.resolve_sync()
    ref_service.create_reference(_sample(citation_key="goodfellow2016deep"))
    resp = client.get("/references/by-citation-key/goodfellow2016deep")
    assert resp.status_code == 200
    assert resp.json()["citation_key"] == "goodfellow2016deep"


def test_by_citation_key_missing_returns_404(client: TestClient) -> None:
    resp = client.get("/references/by-citation-key/doesNotExist123")
    assert resp.status_code == 404


def test_by_citation_key_route_not_shadowed_by_uuid_route(
    client: TestClient,
) -> None:
    ref_service = ReferencesContainer.references_service.resolve_sync()
    ref_service.create_reference(_sample(citation_key="goodfellow2016deep"))
    resp = client.get("/references/by-citation-key/goodfellow2016deep")
    assert resp.status_code == 200


def test_pdf_path_absolute_in_citekey_response(client: TestClient) -> None:
    ref_service = ReferencesContainer.references_service.resolve_sync()
    created = ref_service.create_reference(
        _sample(citation_key="goodfellow2016deep")
    )
    ref_service.set_pdf_path(created.id, "Goodfellow2016DeepLearning.pdf")
    resp = client.get("/references/by-citation-key/goodfellow2016deep")
    assert resp.status_code == 200
    pdf_path = resp.json()["pdf_path"]
    assert pdf_path == str(PDF_DIR / "Goodfellow2016DeepLearning.pdf")
    assert resp.json()["has_pdf"] is True


def test_pdf_path_null_when_no_pdf(client: TestClient) -> None:
    ref_service = ReferencesContainer.references_service.resolve_sync()
    ref_service.create_reference(_sample(citation_key="goodfellow2016deep"))
    resp = client.get("/references/by-citation-key/goodfellow2016deep")
    assert resp.status_code == 200
    assert resp.json()["pdf_path"] is None
    assert resp.json()["has_pdf"] is False


def test_uuid_route_still_works(client: TestClient) -> None:
    ref_service = ReferencesContainer.references_service.resolve_sync()
    created = ref_service.create_reference(
        _sample(citation_key="goodfellow2016deep")
    )
    resp = client.get(f"/references/{created.id}")
    assert resp.status_code == 200
    assert resp.json()["citation_key"] == "goodfellow2016deep"


def test_delete_reference_removes_pdf_from_disk(
    client: TestClient, tmp_path: Path
) -> None:
    ref_service = ReferencesContainer.references_service.resolve_sync()
    ref = ref_service.create_reference(_sample(citation_key="doe2024paper"))
    pdf_store = PdfStore(tmp_path)
    relative = pdf_store.store("paper.pdf", b"%PDF-1.4 bytes")
    ref_service.set_pdf_path(ref.id, str(relative))
    assert (tmp_path / relative).is_file()

    resp = client.delete(f"/references/{ref.id}")
    assert resp.status_code == 204
    assert not (tmp_path / relative).exists()

    gone = client.get(f"/references/{ref.id}")
    assert gone.status_code == 404


def test_delete_reference_without_pdf_succeeds(
    client: TestClient,
) -> None:
    ref_service = ReferencesContainer.references_service.resolve_sync()
    ref = ref_service.create_reference(_sample(citation_key="doe2024paper"))
    resp = client.delete(f"/references/{ref.id}")
    assert resp.status_code == 204
    assert client.get(f"/references/{ref.id}").status_code == 404


def test_delete_missing_reference_returns_404(client: TestClient) -> None:
    resp = client.delete(f"/references/{uuid4()}")
    assert resp.status_code == 404
