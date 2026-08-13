import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.main import app
from app.pdf_store.container import PdfStoreContainer
from app.pdf_store.service import PdfStore
from app.references.container import ReferencesContainer
from app.references.repository import ReferencesRepository
from app.references.service import ReferencesService


@pytest.fixture()
def client(tmp_path: Path) -> Iterator[TestClient]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    session = Session(engine)
    pdf_store = PdfStore(tmp_path)
    ref_service = ReferencesService(ReferencesRepository(session), pdf_store)
    ReferencesContainer.references_service.override_sync(ref_service)
    PdfStoreContainer.pdf_store.override_sync(pdf_store)
    yield TestClient(app)
    ReferencesContainer.references_service.reset_override_sync()
    PdfStoreContainer.pdf_store.reset_override_sync()
    session.close()
    engine.dispose()


def test_ping_accepts_get_and_post(client: TestClient) -> None:
    assert client.get("/connector/ping").status_code == 200
    post = client.post("/connector/ping", json={})
    assert post.status_code == 200
    prefs = post.json()["prefs"]
    # The connector strips all PDF attachments before saveItems when this is falsy.
    assert prefs["downloadAssociatedFiles"] is True
    assert prefs["supportsAttachmentUpload"] is True


def test_get_selected_collection_post_advertises_files_editable(
    client: TestClient,
) -> None:
    resp = client.post("/connector/getSelectedCollection", json={})
    assert resp.status_code == 200
    body = resp.json()
    # The connector only fetches/uploads PDFs when filesEditable is truthy.
    assert body["filesEditable"] is True
    assert body["libraryEditable"] is True
    # progressWindow_inject.js calls response.targets.filter(...) with no
    # null-guard, so targets must be a list.
    assert isinstance(body["targets"], list)


def test_has_attachment_resolvers_accepts_post(client: TestClient) -> None:
    resp = client.post(
        "/connector/hasAttachmentResolvers",
        json={"sessionID": "s", "itemID": "ID1"},
    )
    assert resp.status_code == 200
    assert resp.json() == {"value": False}


def test_connector_roundtrip_persists_pdf(client: TestClient, tmp_path: Path) -> None:
    ref_service = ReferencesContainer.references_service.resolve_sync()
    session_id = "sess-pdf-1"

    save = client.post(
        "/connector/saveItems",
        json={
            "sessionID": session_id,
            "uri": "https://example.com/paper",
            "items": [
                {
                    "id": "ID1",
                    "itemType": "journalArticle",
                    "title": "Connector Paper",
                }
            ],
        },
    )
    assert save.status_code == 201

    pdf_bytes = b"%PDF-1.4 connector bytes"
    attach = client.post(
        f"/connector/saveAttachment?sessionID={session_id}",
        content=pdf_bytes,
        headers={
            "Content-Type": "application/pdf",
            "X-Metadata": json.dumps(
                {
                    "id": "ATT1",
                    "parentItemID": "ID1",
                    "title": "Full Text PDF",
                    "url": "https://example.com/paper.pdf",
                    "contentType": "application/pdf",
                }
            ),
        },
    )
    assert attach.status_code == 201

    references = ref_service.list_all_references()
    assert len(references) == 1
    assert references[0].has_pdf is True

    saved = list(tmp_path.glob("*.pdf"))
    assert len(saved) == 1
    assert saved[0].read_bytes() == pdf_bytes
