import uuid
from datetime import UTC, datetime

from app.references.schemas import ReferenceCreate, ReferenceRead
from app.zotero_import.schemas import ZoteroItem
from app.zotero_import.service import ZoteroImportService


def _fake_reference_read(reference: ReferenceCreate) -> ReferenceRead:
    now = datetime.now(UTC)
    return ReferenceRead(
        id=uuid.uuid4(),
        title=reference.title,
        authors=list(reference.authors),
        year=reference.year,
        citation_key=reference.citation_key or "autogen",
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
    def __init__(self, failing_keys: set[str] | None = None) -> None:
        self.calls: list[ReferenceCreate] = []
        self._seen: set[str] = set()
        self._failing_keys = failing_keys or set()

    def upsert_reference(
        self, reference: ReferenceCreate
    ) -> tuple[ReferenceRead, bool]:
        key = reference.citation_key or f"auto::{reference.title}"
        if key in self._failing_keys:
            msg = f"boom on {key}"
            raise RuntimeError(msg)
        self.calls.append(reference)
        created = key not in self._seen
        self._seen.add(key)
        return _fake_reference_read(reference), created


class FakeZoteroClient:
    def __init__(
        self,
        items: list[ZoteroItem],
        keys: dict[str, str] | None = None,
    ) -> None:
        self._items = items
        self._keys = keys or {}

    def list_items(self) -> list[ZoteroItem]:
        return list(self._items)

    def citation_keys(self, item_keys: list[str]) -> dict[str, str]:
        return dict(self._keys)


def _zotero_item(
    key: str,
    *,
    item_type: str = "journalArticle",
    title: str = "A Paper",
    date: str | None = "2024-05-01",
    first_name: str | None = "Jane",
    last_name: str | None = "Doe",
    name: str | None = None,
    doi: str | None = "10.1234/example",
    url: str = "https://example.com/paper",
    publication_title: str | None = "Nature",
    publisher: str | None = "Springer",
    volume: str | None = "12",
    issue: str | None = "3",
    pages: str | None = "45-67",
    language: str | None = "en",
    abstract_note: str | None = "An abstract.",
) -> ZoteroItem:
    creator: dict[str, str] = {"creatorType": "author"}
    if name is not None:
        creator["name"] = name
    else:
        creator["firstName"] = first_name or ""
        creator["lastName"] = last_name or ""
    data: dict[str, object] = {
        "key": key,
        "itemType": item_type,
        "title": title,
        "creators": [creator],
        "date": date,
        "DOI": doi,
        "url": url,
        "publicationTitle": publication_title,
        "publisher": publisher,
        "volume": volume,
        "issue": issue,
        "pages": pages,
        "language": language,
        "abstractNote": abstract_note,
    }
    return ZoteroItem.model_validate(data)


def _make_service(
    items: list[ZoteroItem],
    keys: dict[str, str] | None = None,
    failing_keys: set[str] | None = None,
) -> tuple[ZoteroImportService, FakeReferencesService]:
    fake_refs = FakeReferencesService(failing_keys=failing_keys)
    service = ZoteroImportService(
        client=FakeZoteroClient(items, keys),
        references_service=fake_refs,  # type: ignore[arg-type]
    )
    return service, fake_refs


def test_field_mapping_correctness() -> None:
    item = _zotero_item("KEY1", title="Deep Learning", date="2016-12-01")
    service, fake_refs = _make_service([item], keys={"KEY1": "goodfellow2016deep"})
    result = service.import_all()
    assert result.imported == 1
    assert result.errors == []
    create = fake_refs.calls[0]
    assert create.title == "Deep Learning"
    assert create.authors == ["Jane Doe"]
    assert create.year == 2016
    assert create.doi == "10.1234/example"
    assert create.url == "https://example.com/paper"
    assert create.publication_title == "Nature"
    assert create.publisher == "Springer"
    assert create.volume == "12"
    assert create.issue == "3"
    assert create.pages == "45-67"
    assert create.language == "en"
    assert create.abstract_note == "An abstract."


def test_bbt_citation_key_preserved_end_to_end() -> None:
    item = _zotero_item("KEY1")
    service, fake_refs = _make_service([item], keys={"KEY1": "doe2024paper"})
    service.import_all()
    assert fake_refs.calls[0].citation_key == "doe2024paper"


def test_missing_bbt_key_passes_none_for_autogen() -> None:
    item = _zotero_item("KEY1")
    service, fake_refs = _make_service([item], keys={})
    service.import_all()
    assert fake_refs.calls[0].citation_key is None


def test_second_run_counts_updated_not_imported() -> None:
    item = _zotero_item("KEY1")
    service, fake_refs = _make_service([item], keys={"KEY1": "doe2024paper"})
    first = service.import_all()
    second = service.import_all()
    assert first.imported == 1
    assert first.updated == 0
    assert second.imported == 0
    assert second.updated == 1
    assert len(fake_refs.calls) == 2


def test_per_item_error_isolation_records_error() -> None:
    good = _zotero_item("GOOD", title="Good Paper")
    bad = _zotero_item("BAD", title="Bad Paper")
    service, fake_refs = _make_service(
        [good, bad],
        keys={"GOOD": "good1", "BAD": "bad1"},
        failing_keys={"auto::Bad Paper"},
    )
    result = service.import_all()
    assert result.imported == 1
    assert len(result.errors) == 1
    assert "BAD" in result.errors[0]
    assert [c.title for c in fake_refs.calls] == ["Good Paper"]


def test_attachment_and_note_items_are_filtered_out() -> None:
    attachment = _zotero_item("ATT", item_type="attachment", title="pdf.pdf")
    note = _zotero_item("NOTE", item_type="note", title="a note")
    real = _zotero_item("REAL", title="Real Paper")
    service, fake_refs = _make_service(
        [attachment, note, real], keys={"REAL": "real1"}
    )
    result = service.import_all()
    assert result.skipped == 2
    assert result.imported == 1
    assert [c.title for c in fake_refs.calls] == ["Real Paper"]


def test_organization_author_with_name_field() -> None:
    item = _zotero_item(
        "ORG1",
        title="Org Report",
        name="World Health Organization",
        first_name=None,
        last_name=None,
        date="2020-01-01",
    )
    service, fake_refs = _make_service([item], keys={"ORG1": "who2020report"})
    result = service.import_all()
    assert result.imported == 1
    assert fake_refs.calls[0].authors == ["World Health Organization"]
    assert fake_refs.calls[0].year == 2020


def test_per_item_error_isolation_records_error() -> None:
    good = _zotero_item("GOOD", title="Good Paper")
    bad = _zotero_item("BAD", title="Bad Paper")
    service, fake_refs = _make_service(
        [good, bad],
        keys={"GOOD": "good1", "BAD": "bad1"},
        failing_keys={"bad1"},
    )

def test_empty_doi_and_url_normalized_to_none() -> None:
    item = _zotero_item("KEY1", doi="", url="")
    service, fake_refs = _make_service([item], keys={"KEY1": "k1"})
    service.import_all()
    assert fake_refs.calls[0].doi is None
    assert fake_refs.calls[0].url is None


def test_non_author_creators_excluded_from_authors() -> None:
    data = {
        "key": "KEY1",
        "itemType": "journalArticle",
        "title": "Edited Work",
        "creators": [
            {"creatorType": "editor", "firstName": "Ed", "lastName": "Itor"},
            {"creatorType": "author", "firstName": "Jane", "lastName": "Doe"},
        ],
        "date": "2021",
        "DOI": "10.1234/x",
        "url": "https://e.com",
    }
    items = [ZoteroItem.model_validate(data)]
    service, fake_refs = _make_service(items, keys={"KEY1": "doe2021edited"})
    service.import_all()
    assert fake_refs.calls[0].authors == ["Jane Doe"]
