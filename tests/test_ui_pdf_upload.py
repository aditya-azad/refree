from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.main import app
from app.pdf_store.service import PdfStore
from app.references.container import ReferencesContainer
from app.references.repository import ReferencesRepository
from app.references.schemas import ReferenceCreate
from app.references.service import ReferencesService
from app.search.container import SearchContainer
from app.search.service import SearchService
from app.ui.container import UIContainer


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
    UIContainer.ui_service.reset_override_sync()
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


def test_attach_pdf_renders_details_and_stores_file(
    client: TestClient, tmp_path: Path
) -> None:
    ref_service = ReferencesContainer.references_service.resolve_sync()
    ref = ref_service.create_reference(
        _sample(citation_key="goodfellow2016deep")
    )

    resp = client.post(
        f"/ui/reference/{ref.id}/pdf",
        files={"file": ("paper.pdf", b"%PDF-1.4 test bytes", "application/pdf")},
    )
    assert resp.status_code == 200
    body = resp.text
    assert "Open PDF" in body
    assert "Replace PDF" in body

    stored = next(tmp_path.glob("*.pdf"))

    reloaded = ref_service.get_reference(ref.id)
    assert reloaded.has_pdf


def test_attach_pdf_replaces_existing_pdf(
    client: TestClient, tmp_path: Path
) -> None:
    ref_service = ReferencesContainer.references_service.resolve_sync()
    ref = ref_service.create_reference(
        _sample(citation_key="goodfellow2016deep")
    )
    client.post(
        f"/ui/reference/{ref.id}/pdf",
        files={"file": ("v1.pdf", b"%PDF-1.4 first", "application/pdf")},
    )
    first = next(tmp_path.glob("*.pdf"))
    first_bytes = first.read_bytes()
    assert first_bytes == b"%PDF-1.4 first"

    client.post(
        f"/ui/reference/{ref.id}/pdf",
        files={"file": ("v2.pdf", b"%PDF-1.4 second", "application/pdf")},
    )
    pdfs = list(tmp_path.glob("*.pdf"))
    assert len(pdfs) == 1
    assert pdfs[0].read_bytes() == b"%PDF-1.4 second"


def test_attach_pdf_rejects_non_pdf(client: TestClient) -> None:
    ref_service = ReferencesContainer.references_service.resolve_sync()
    ref = ref_service.create_reference(
        _sample(citation_key="goodfellow2016deep")
    )
    resp = client.post(
        f"/ui/reference/{ref.id}/pdf",
        files={"file": ("not.txt", b"plain text", "text/plain")},
    )
    assert resp.status_code == 422
    reloaded = ref_service.get_reference(ref.id)
    assert not reloaded.has_pdf


def test_attach_pdf_missing_reference_returns_404(client: TestClient) -> None:
    from uuid import uuid4

    resp = client.post(
        f"/ui/reference/{uuid4()}/pdf",
        files={"file": ("paper.pdf", b"%PDF-1.4", "application/pdf")},
    )
    assert resp.status_code == 404
