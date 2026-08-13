import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.pdf_store.service import PdfStore
from app.references.schemas import ReferenceCreate, ReferenceRead
from app.zotero_browser_plugin.schemas import (
    ConnectorAttachmentMetadata,
    ConnectorItem,
)
from app.zotero_browser_plugin.service import ZoteroBrowserPluginService
from app.zotero_browser_plugin.session import ConnectorSessionRegistry


def _fake_reference_read(reference: ReferenceCreate) -> ReferenceRead:
    now = datetime.now(UTC)
    return ReferenceRead(
        id=uuid.uuid4(),
        title=reference.title,
        authors=list(reference.authors),
        year=reference.year,
        citation_key="fake",
        doi=reference.doi,
        url=reference.url,
        publication_title=reference.publication_title,
        publisher=reference.publisher,
        volume=reference.volume,
        issue=reference.issue,
        pages=reference.pages,
        language=reference.language,
        abstract_note=reference.abstract_note,
        pdf_path=None,
        created_at=now,
        updated_at=now,
    )


class FakeReferencesService:
    def __init__(self) -> None:
        self.created: list[ReferenceCreate] = []
        self.pdf_paths: list[tuple[uuid.UUID, str]] = []

    def create_reference(self, reference: ReferenceCreate) -> ReferenceRead:
        self.created.append(reference)
        return _fake_reference_read(reference)

    def set_pdf_path(
        self, reference_id: uuid.UUID, pdf_path: str
    ) -> ReferenceRead:
        self.pdf_paths.append((reference_id, pdf_path))
        return _fake_reference_read(ReferenceCreate(title="updated"))


def _item(
    key: str,
    title: str = "A Paper",
    item_id: str = "IDAAA",
    date: str | None = None,
    last_name: str = "Doe",
) -> ConnectorItem:
    return ConnectorItem.model_validate(
        {
            "itemType": "journalArticle",
            "title": title,
            "id": item_id,
            "key": key,
            "date": date,
            "creators": [
                {
                    "creatorType": "author",
                    "firstName": "Jane",
                    "lastName": last_name,
                }
            ],
            "DOI": "10.1234/example",
            "url": "https://example.com/paper",
        }
    )


def test_ingest_items_persists_and_returns_saved_references(
    tmp_path: Path,
) -> None:
    fake_refs = FakeReferencesService()
    registry = ConnectorSessionRegistry()
    service = ZoteroBrowserPluginService(
        fake_refs, registry, PdfStore(tmp_path)
    )

    result = service.ingest_items(
        "sess-1",
        [_item("KEYAAA", item_id="ID1"), _item("KEYBBB", item_id="ID2")],
    )

    assert len(result) == 2
    assert all(r.reference_id is not None for r in result)
    assert len(fake_refs.created) == 2
    assert fake_refs.created[0].title == "A Paper"
    assert fake_refs.created[0].doi == "10.1234/example"
    assert fake_refs.created[0].url == "https://example.com/paper"


def test_ingest_items_registers_references_in_session(tmp_path: Path) -> None:
    fake_refs = FakeReferencesService()
    registry = ConnectorSessionRegistry()
    service = ZoteroBrowserPluginService(
        fake_refs, registry, PdfStore(tmp_path)
    )

    service.ingest_items(
        "sess-1",
        [_item("KEYAAA", item_id="ID1"), _item("KEYBBB", item_id="ID2")],
    )

    session = registry.get("sess-1")
    assert session is not None
    assert set(session.entries.keys()) == {"ID1", "ID2"}
    assert session.entries["ID1"].item.key == "KEYAAA"
    assert session.entries["ID1"].item.item_id == "ID1"


def test_different_sessions_do_not_cross_contaminate(tmp_path: Path) -> None:
    fake_refs = FakeReferencesService()
    registry = ConnectorSessionRegistry()
    service = ZoteroBrowserPluginService(
        fake_refs, registry, PdfStore(tmp_path)
    )

    service.ingest_items("sess-1", [_item("KEYAAA", item_id="ID1")])
    service.ingest_items("sess-2", [_item("KEYBBB", item_id="ID2")])

    sess1 = registry.get("sess-1")
    sess2 = registry.get("sess-2")
    assert sess1 is not None
    assert sess2 is not None
    assert set(sess1.entries.keys()) == {"ID1"}
    assert set(sess2.entries.keys()) == {"ID2"}


def test_ingest_items_handles_missing_key(tmp_path: Path) -> None:
    fake_refs = FakeReferencesService()
    registry = ConnectorSessionRegistry()
    service = ZoteroBrowserPluginService(
        fake_refs, registry, PdfStore(tmp_path)
    )

    item = ConnectorItem.model_validate(
        {"itemType": "journalArticle", "title": "No Key Paper", "id": "IDX"}
    )
    result = service.ingest_items("sess-1", [item])

    assert result[0].reference_id is not None
    assert fake_refs.created[0].title == "No Key Paper"


def test_attach_pdf_naming_uses_author_year_title(tmp_path: Path) -> None:
    fake_refs = FakeReferencesService()
    registry = ConnectorSessionRegistry()
    service = ZoteroBrowserPluginService(
        fake_refs, registry, PdfStore(tmp_path)
    )

    saved = service.ingest_items(
        "sess-1",
        [
            _item(
                "KEYAAA",
                title="A Paper",
                item_id="ID1",
                date="2026-03-15",
                last_name="Yang",
            )
        ],
    )
    parent_id = saved[0].reference_id

    meta = ConnectorAttachmentMetadata.model_validate(
        {
            "parentItemID": "ID1",
            "title": "Full Text PDF",
            "url": "https://x/y.pdf",
        }
    )
    attachment = service.attach_pdf("sess-1", meta, b"%PDF-1.4 bytes")

    assert attachment.reference_id == parent_id
    assert attachment.path == Path("Yang2026APaper.pdf")
    assert (tmp_path / attachment.path).read_bytes() == b"%PDF-1.4 bytes"


def test_attach_pdf_naming_without_date(tmp_path: Path) -> None:
    fake_refs = FakeReferencesService()
    registry = ConnectorSessionRegistry()
    service = ZoteroBrowserPluginService(
        fake_refs, registry, PdfStore(tmp_path)
    )

    service.ingest_items("sess-1", [_item("KEYAAA", item_id="ID1")])
    meta = ConnectorAttachmentMetadata.model_validate(
        {"parentItemID": "ID1", "title": "Full Text PDF"}
    )
    attachment = service.attach_pdf("sess-1", meta, b"%PDF-1.4")

    assert attachment.path == Path("DoeAPaper.pdf")


def test_attach_pdf_naming_falls_back_to_untitled(tmp_path: Path) -> None:
    fake_refs = FakeReferencesService()
    registry = ConnectorSessionRegistry()
    service = ZoteroBrowserPluginService(
        fake_refs, registry, PdfStore(tmp_path)
    )

    item = ConnectorItem.model_validate(
        {"itemType": "journalArticle", "title": "", "id": "ID1"}
    )
    service.ingest_items("sess-1", [item])
    meta = ConnectorAttachmentMetadata.model_validate(
        {"parentItemID": "ID1", "title": "Full Text PDF"}
    )
    attachment = service.attach_pdf("sess-1", meta, b"%PDF-1.4")

    assert attachment.path == Path("untitled.pdf")


def test_attach_pdf_naming_uses_first_author(tmp_path: Path) -> None:
    fake_refs = FakeReferencesService()
    registry = ConnectorSessionRegistry()
    service = ZoteroBrowserPluginService(
        fake_refs, registry, PdfStore(tmp_path)
    )

    item = ConnectorItem.model_validate(
        {
            "itemType": "journalArticle",
            "title": "On Graphs",
            "id": "ID1",
            "date": "2025",
            "creators": [
                {
                    "creatorType": "author",
                    "firstName": "Jane",
                    "lastName": "Yang",
                },
                {
                    "creatorType": "author",
                    "firstName": "Bob",
                    "lastName": "Smith",
                },
                {
                    "creatorType": "editor",
                    "firstName": "Ed",
                    "lastName": "Jones",
                },
            ],
        }
    )
    service.ingest_items("sess-1", [item])
    meta = ConnectorAttachmentMetadata.model_validate(
        {"parentItemID": "ID1", "title": "Full Text PDF"}
    )
    attachment = service.attach_pdf("sess-1", meta, b"%PDF-1.4")

    assert attachment.path == Path("Yang2025OnGraphs.pdf")


def test_attach_pdf_deduplicates_collisions(tmp_path: Path) -> None:
    fake_refs = FakeReferencesService()
    registry = ConnectorSessionRegistry()
    service = ZoteroBrowserPluginService(
        fake_refs, registry, PdfStore(tmp_path)
    )

    service.ingest_items("sess-1", [_item("KEYAAA", item_id="ID1")])
    meta = ConnectorAttachmentMetadata.model_validate(
        {"parentItemID": "ID1", "title": "Full Text PDF"}
    )
    first = service.attach_pdf("sess-1", meta, b"%PDF-1.4 first")
    service.ingest_items("sess-2", [_item("KEYAAA", item_id="ID2")])
    meta2 = ConnectorAttachmentMetadata.model_validate(
        {"parentItemID": "ID2", "title": "Full Text PDF"}
    )
    second = service.attach_pdf("sess-2", meta2, b"%PDF-1.4 second")

    assert first.path == Path("DoeAPaper.pdf")
    assert second.path == Path("DoeAPaper_1.pdf")
    assert (tmp_path / first.path).read_bytes() == b"%PDF-1.4 first"
    assert (tmp_path / second.path).read_bytes() == b"%PDF-1.4 second"


def test_attach_pdf_raises_when_parent_missing(tmp_path: Path) -> None:
    fake_refs = FakeReferencesService()
    registry = ConnectorSessionRegistry()
    service = ZoteroBrowserPluginService(
        fake_refs, registry, PdfStore(tmp_path)
    )

    meta = ConnectorAttachmentMetadata.model_validate(
        {"parentItemID": "NOPE", "title": "Full Text PDF"}
    )
    with pytest.raises(ValueError):
        service.attach_pdf("sess-1", meta, b"%PDF-1.4 bytes")


def test_attach_pdf_raises_when_session_missing(tmp_path: Path) -> None:
    fake_refs = FakeReferencesService()
    registry = ConnectorSessionRegistry()
    service = ZoteroBrowserPluginService(
        fake_refs, registry, PdfStore(tmp_path)
    )

    meta = ConnectorAttachmentMetadata.model_validate(
        {"parentItemID": "ID1", "title": "Full Text PDF"}
    )
    with pytest.raises(ValueError):
        service.attach_pdf("unknown-session", meta, b"%PDF-1.4 bytes")


def test_save_standalone_pdf_creates_reference_and_stores_file(
    tmp_path: Path,
) -> None:
    fake_refs = FakeReferencesService()
    registry = ConnectorSessionRegistry()
    service = ZoteroBrowserPluginService(
        fake_refs, registry, PdfStore(tmp_path)
    )

    meta = ConnectorAttachmentMetadata.model_validate(
        {"title": "Standalone PDF", "url": "https://x/y.pdf"}
    )
    attachment = service.save_standalone_pdf(
        "sess-1", meta, b"%PDF-1.4 standalone"
    )

    assert attachment.path == Path("StandalonePDF.pdf")
    assert (tmp_path / attachment.path).read_bytes() == b"%PDF-1.4 standalone"
    assert len(fake_refs.created) == 1
    assert fake_refs.created[0].title == "Standalone PDF"


def test_save_standalone_pdf_defaults_title(tmp_path: Path) -> None:
    fake_refs = FakeReferencesService()
    registry = ConnectorSessionRegistry()
    service = ZoteroBrowserPluginService(
        fake_refs, registry, PdfStore(tmp_path)
    )

    meta = ConnectorAttachmentMetadata.model_validate(
        {"url": "https://x/y.pdf"}
    )
    attachment = service.save_standalone_pdf("sess-1", meta, b"%PDF-1.4")
    assert attachment.path == Path("UntitledAttachment.pdf")
    assert fake_refs.created[0].title == "Untitled Attachment"


def test_attach_pdf_creates_pdf_dir_if_missing(tmp_path: Path) -> None:
    fake_refs = FakeReferencesService()
    registry = ConnectorSessionRegistry()
    pdf_dir = tmp_path / "pdfs"
    service = ZoteroBrowserPluginService(fake_refs, registry, PdfStore(pdf_dir))

    service.ingest_items("sess-1", [_item("KEYAAA", item_id="ID1")])
    meta = ConnectorAttachmentMetadata.model_validate(
        {"parentItemID": "ID1", "title": "Full Text PDF"}
    )
    attachment = service.attach_pdf("sess-1", meta, b"%PDF-1.4")

    assert pdf_dir.is_dir()
    assert (pdf_dir / attachment.path).is_file()
