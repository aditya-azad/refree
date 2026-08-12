import uuid
from datetime import UTC, datetime

import pytest

from app.references.schemas import ItemCreate, ItemRead
from app.zotero_browser_plugin.schemas import ConnectorItem
from app.zotero_browser_plugin.service import ZoteroBrowserPluginService
from app.zotero_browser_plugin.session import ConnectorSessionRegistry


class FakeReferencesService:
    def __init__(self) -> None:
        self.created: list[ItemCreate] = []

    def create_item(self, item: ItemCreate) -> ItemRead:
        self.created.append(item)
        return ItemRead(
            id=uuid.uuid4(),
            name=item.name,
            description=item.description,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )


def _item(key: str, title: str = "A Paper") -> ConnectorItem:
    return ConnectorItem.model_validate(
        {
            "itemType": "journalArticle",
            "title": title,
            "key": key,
            "creators": [
                {"creatorType": "author", "firstName": "Jane", "lastName": "Doe"}
            ],
            "DOI": "10.1234/example",
            "url": "https://example.com/paper",
        }
    )


def test_ingest_items_persists_and_returns_saved_references() -> None:
    fake_refs = FakeReferencesService()
    registry = ConnectorSessionRegistry()
    service = ZoteroBrowserPluginService(fake_refs, registry)

    result = service.ingest_items("sess-1", [_item("KEYAAA"), _item("KEYBBB")])

    assert len(result) == 2
    assert [r.zotero_key for r in result] == ["KEYAAA", "KEYBBB"]
    assert all(r.bibtex == "" for r in result)
    assert all(r.reference_id is not None for r in result)
    assert len(fake_refs.created) == 2
    assert fake_refs.created[0].name == "A Paper"
    assert fake_refs.created[0].description == "KEYAAA"


def test_ingest_items_registers_references_in_session() -> None:
    fake_refs = FakeReferencesService()
    registry = ConnectorSessionRegistry()
    service = ZoteroBrowserPluginService(fake_refs, registry)

    service.ingest_items("sess-1", [_item("KEYAAA"), _item("KEYBBB")])

    session = registry.get("sess-1")
    assert session is not None
    assert [r.zotero_key for r in session.references] == ["KEYAAA", "KEYBBB"]


def test_different_sessions_do_not_cross_contaminate() -> None:
    fake_refs = FakeReferencesService()
    registry = ConnectorSessionRegistry()
    service = ZoteroBrowserPluginService(fake_refs, registry)

    service.ingest_items("sess-1", [_item("KEYAAA")])
    service.ingest_items("sess-2", [_item("KEYBBB")])

    sess1 = registry.get("sess-1")
    sess2 = registry.get("sess-2")
    assert sess1 is not None
    assert sess2 is not None
    assert [r.zotero_key for r in sess1.references] == ["KEYAAA"]
    assert [r.zotero_key for r in sess2.references] == ["KEYBBB"]


def test_ingest_items_handles_missing_key() -> None:
    fake_refs = FakeReferencesService()
    registry = ConnectorSessionRegistry()
    service = ZoteroBrowserPluginService(fake_refs, registry)

    item = ConnectorItem.model_validate(
        {"itemType": "journalArticle", "title": "No Key Paper"}
    )
    result = service.ingest_items("sess-1", [item])

    assert result[0].zotero_key == ""
    assert fake_refs.created[0].description == ""


def test_attach_pdf_raises_not_implemented() -> None:
    fake_refs = FakeReferencesService()
    registry = ConnectorSessionRegistry()
    service = ZoteroBrowserPluginService(fake_refs, registry)

    with pytest.raises(NotImplementedError):
        service.attach_pdf("sess-1", {}, b"")
