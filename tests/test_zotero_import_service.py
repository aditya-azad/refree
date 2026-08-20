import uuid
from datetime import UTC, datetime
from pathlib import Path

from app.pdf_store.service import PdfStore
from app.references.schemas import ReferenceCreate, ReferenceRead
from app.zotero_import.schemas import ZoteroAttachment, ZoteroItem
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
        item_type=reference.item_type,
        pdf_path=None,
        created_at=now,
        updated_at=now,
    )


class FakeReferencesService:
    def __init__(self, failing_keys: set[str] | None = None) -> None:
        self.calls: list[ReferenceCreate] = []
        self._failing_keys = failing_keys or set()
        self._by_key: dict[str, ReferenceRead] = {}
        self.pdf_paths: dict[uuid.UUID, str] = {}

    def upsert_reference(
        self, reference: ReferenceCreate
    ) -> tuple[ReferenceRead, bool]:
        key = reference.citation_key or f"auto::{reference.title}"
        if key in self._failing_keys:
            msg = f"boom on {key}"
            raise RuntimeError(msg)
        self.calls.append(reference)
        existing = self._by_key.get(key)
        if existing is not None:
            return existing, False
        ref = _fake_reference_read(reference)
        self._by_key[key] = ref
        return ref, True

    def set_pdf_path(self, reference_id: uuid.UUID, pdf_path: str) -> None:
        self.pdf_paths[reference_id] = pdf_path
        for ref in self._by_key.values():
            if ref.id == reference_id:
                ref.pdf_path = pdf_path
                return


class FakeZoteroClient:
    def __init__(
        self,
        items: list[ZoteroItem],
        keys: dict[str, str] | None = None,
        attachments: list[ZoteroAttachment] | None = None,
    ) -> None:
        self._items = items
        self._keys = keys or {}
        self._attachments = attachments or []

    def list_items(self) -> list[ZoteroItem]:
        return list(self._items)

    def citation_keys(self, item_keys: list[str]) -> dict[str, str]:
        return dict(self._keys)

    def list_pdf_attachments(self) -> list[ZoteroAttachment]:
        return list(self._attachments)


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
    attachments: list[ZoteroAttachment] | None = None,
    pdf_dir: Path | None = None,
    zotero_storage_dir: Path | None = None,
) -> tuple[ZoteroImportService, FakeReferencesService]:
    fake_refs = FakeReferencesService(failing_keys=failing_keys)
    service = ZoteroImportService(
        client=FakeZoteroClient(
            items,
            keys,
            attachments=attachments,
        ),
        references_service=fake_refs,  # type: ignore[arg-type]
        pdf_store=PdfStore(pdf_dir or Path("/tmp/refree-test-pdfs")),
        zotero_storage_dir=zotero_storage_dir
        or Path("/tmp/refree-test-storage"),
    )
    return service, fake_refs


def test_field_mapping_correctness() -> None:
    item = _zotero_item("KEY1", title="Deep Learning", date="2016-12-01")
    service, fake_refs = _make_service(
        [item], keys={"KEY1": "goodfellow2016deep"}
    )
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


def test_item_type_persisted_for_journal_article(
    tmp_path: Path,
) -> None:
    item = _zotero_item(
        "SHANNON1948",
        item_type="journalArticle",
        title="A Mathematical Theory of Communication",
        date="1948-07",
        first_name="Claude E.",
        last_name="Shannon",
        doi="10.1002/j.1538-7305.1948.tb01338.x",
        url="https://ieeexplore.ieee.org/document/6773024",
        publication_title="Bell System Technical Journal",
        publisher="American Telephone and Telegraph Company",
        volume="27",
        issue="3",
        pages="379-423",
    )
    service, fake_refs = _make_service(
        [item],
        keys={"SHANNON1948": "shannon1948mathematical"},
        pdf_dir=tmp_path / "pdfs",
        zotero_storage_dir=tmp_path / "storage",
    )
    service.import_all()
    assert fake_refs.calls[0].item_type == "journalArticle"


def test_item_type_persisted_distinctly_for_book_section(
    tmp_path: Path,
) -> None:
    item = _zotero_item(
        "GAMMA1994",
        item_type="bookSection",
        title="Introduction",
        date="1994-10-31",
        first_name="Erich",
        last_name="Gamma",
        doi=None,
        url="https://www.informit.com/store/design-patterns-9780201633610",
        publication_title="Design Patterns: Elements of Reusable Object-Oriented Software",
        publisher="Addison-Wesley Professional",
        pages="1-22",
    )
    service, fake_refs = _make_service(
        [item],
        keys={"GAMMA1994": "gamma1994introduction"},
        pdf_dir=tmp_path / "pdfs",
        zotero_storage_dir=tmp_path / "storage",
    )
    service.import_all()
    assert fake_refs.calls[0].item_type == "bookSection"
    assert fake_refs.calls[0].item_type != "journalArticle"


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
    assert result.skipped == 0
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


def _pdf_attachment(
    key: str,
    parent_key: str | None,
    storage_dir: Path,
    *,
    content: bytes = b"%PDF-1.4 bytes",
) -> ZoteroAttachment:
    filename = f"{key}.pdf"
    file_path = storage_dir / key / filename
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_bytes(content)
    data: dict[str, object] = {
        "key": key,
        "itemType": "attachment",
        "contentType": "application/pdf",
        "title": filename,
        "path": f"storage:{filename}",
    }
    if parent_key is not None:
        data["parentItem"] = parent_key
    return ZoteroAttachment.model_validate(data)


def test_pdf_attachment_read_and_stored(tmp_path: Path) -> None:
    storage = tmp_path / "zotero"
    pdfs = tmp_path / "pdfs"
    item = _zotero_item("PARENT", title="Deep Learning")
    attachment = _pdf_attachment(
        "ATT1", "PARENT", storage, content=b"%PDF-1.4 bytes"
    )
    service, fake_refs = _make_service(
        [item],
        keys={"PARENT": "doe2024deeplearning"},
        attachments=[attachment],
        pdf_dir=pdfs,
        zotero_storage_dir=storage,
    )
    result = service.import_all()
    assert result.imported == 1
    assert result.pdfs_imported == 1
    assert len(fake_refs.pdf_paths) == 1
    stored = list(pdfs.glob("*.pdf"))
    assert len(stored) == 1
    assert stored[0].read_bytes() == b"%PDF-1.4 bytes"


def test_pdf_filename_built_from_author_year_title(tmp_path: Path) -> None:
    storage = tmp_path / "zotero"
    pdfs = tmp_path / "pdfs"
    item = _zotero_item("PARENT", title="A Paper", date="2024-05-01")
    attachment = _pdf_attachment("ATT1", "PARENT", storage)
    service, fake_refs = _make_service(
        [item],
        keys={"PARENT": "doe2024paper"},
        attachments=[attachment],
        pdf_dir=pdfs,
        zotero_storage_dir=storage,
    )
    service.import_all()
    stored = list(pdfs.glob("*.pdf"))
    assert len(stored) == 1
    assert stored[0].name == "Doe2024APaper.pdf"


def test_orphan_pdf_attachment_without_parent_is_skipped(
    tmp_path: Path,
) -> None:
    storage = tmp_path / "zotero"
    pdfs = tmp_path / "pdfs"
    item = _zotero_item("PARENT", title="A Paper")
    orphan = _pdf_attachment("ORPHAN", "MISSING", storage)
    standalone = _pdf_attachment("STANDALONE", None, storage)
    service, fake_refs = _make_service(
        [item],
        keys={"PARENT": "doe2024paper"},
        attachments=[orphan, standalone],
        pdf_dir=pdfs,
        zotero_storage_dir=storage,
    )
    result = service.import_all()
    assert result.pdfs_imported == 0
    assert result.pdfs_skipped == 2
    assert fake_refs.pdf_paths == {}


def test_existing_pdf_path_not_reimported(tmp_path: Path) -> None:
    storage = tmp_path / "zotero"
    pdfs = tmp_path / "pdfs"
    item = _zotero_item("PARENT", title="A Paper")
    attachment = _pdf_attachment("ATT1", "PARENT", storage)
    service, fake_refs = _make_service(
        [item],
        keys={"PARENT": "doe2024paper"},
        attachments=[attachment],
        pdf_dir=pdfs,
        zotero_storage_dir=storage,
    )
    first = service.import_all()
    assert first.pdfs_imported == 1
    second = service.import_all()
    assert second.pdfs_imported == 0
    assert second.pdfs_skipped == 1
    assert len(list(pdfs.glob("*.pdf"))) == 1


def test_linked_pdf_attachment_resolved_by_absolute_path(
    tmp_path: Path,
) -> None:
    storage = tmp_path / "zotero"
    pdfs = tmp_path / "pdfs"
    linked = tmp_path / "linked.pdf"
    linked.write_bytes(b"%PDF-1.4 linked")
    item = _zotero_item("PARENT", title="A Paper")
    data: dict[str, object] = {
        "key": "ATT1",
        "itemType": "attachment",
        "contentType": "application/pdf",
        "title": "linked.pdf",
        "path": str(linked),
        "parentItem": "PARENT",
    }
    attachment = ZoteroAttachment.model_validate(data)
    service, fake_refs = _make_service(
        [item],
        keys={"PARENT": "doe2024paper"},
        attachments=[attachment],
        pdf_dir=pdfs,
        zotero_storage_dir=storage,
    )
    result = service.import_all()
    assert result.pdfs_imported == 1
    stored = list(pdfs.glob("*.pdf"))
    assert len(stored) == 1
    assert stored[0].read_bytes() == b"%PDF-1.4 linked"


def test_attachment_with_unresolvable_path_is_skipped(tmp_path: Path) -> None:
    storage = tmp_path / "zotero"
    pdfs = tmp_path / "pdfs"
    item = _zotero_item("PARENT", title="A Paper")
    data: dict[str, object] = {
        "key": "ATT1",
        "itemType": "attachment",
        "contentType": "application/pdf",
        "title": "gone.pdf",
        "parentItem": "PARENT",
    }
    attachment = ZoteroAttachment.model_validate(data)
    service, _ = _make_service(
        [item],
        keys={"PARENT": "doe2024paper"},
        attachments=[attachment],
        pdf_dir=pdfs,
        zotero_storage_dir=storage,
    )
    result = service.import_all()
    assert result.pdfs_imported == 0
    assert result.pdfs_skipped == 1


def test_missing_storage_file_error_isolated_and_recorded(
    tmp_path: Path,
) -> None:
    storage = tmp_path / "zotero"
    pdfs = tmp_path / "pdfs"
    item = _zotero_item("PARENT", title="A Paper")
    data: dict[str, object] = {
        "key": "ATT1",
        "itemType": "attachment",
        "contentType": "application/pdf",
        "title": "missing.pdf",
        "path": "storage:missing.pdf",
        "parentItem": "PARENT",
    }
    attachment = ZoteroAttachment.model_validate(data)
    service, _ = _make_service(
        [item],
        keys={"PARENT": "doe2024paper"},
        attachments=[attachment],
        pdf_dir=pdfs,
        zotero_storage_dir=storage,
    )
    result = service.import_all()
    assert result.pdfs_imported == 0
    assert any("ATT1" in err for err in result.errors)


def test_linked_pdf_with_dedup_suffix_resolves_without_suffix(
    tmp_path: Path,
) -> None:
    storage = tmp_path / "zotero"
    pdfs = tmp_path / "pdfs"
    actual = tmp_path / "papers" / "Doe2024APaper.pdf"
    actual.parent.mkdir(parents=True)
    actual.write_bytes(b"%PDF-1.4 deduped")
    item = _zotero_item("PARENT", title="A Paper", date="2024-05-01")
    data: dict[str, object] = {
        "key": "ATT1",
        "itemType": "attachment",
        "contentType": "application/pdf",
        "title": "Doe2024APaper 1.pdf",
        "path": str(tmp_path / "papers" / "Doe2024APaper 1.pdf"),
        "parentItem": "PARENT",
    }
    attachment = ZoteroAttachment.model_validate(data)
    service, _ = _make_service(
        [item],
        keys={"PARENT": "doe2024paper"},
        attachments=[attachment],
        pdf_dir=pdfs,
        zotero_storage_dir=storage,
    )
    result = service.import_all()
    assert result.pdfs_imported == 1
    stored = list(pdfs.glob("*.pdf"))
    assert len(stored) == 1
    assert stored[0].read_bytes() == b"%PDF-1.4 deduped"


def test_imported_file_attachment_without_path_resolved_from_storage(
    tmp_path: Path,
) -> None:
    storage = tmp_path / "zotero"
    pdfs = tmp_path / "pdfs"
    stored = storage / "ATT1" / "paper.pdf"
    stored.parent.mkdir(parents=True)
    stored.write_bytes(b"%PDF-1.4 stored")
    item = _zotero_item("PARENT", title="A Paper", date="2024-05-01")
    data: dict[str, object] = {
        "key": "ATT1",
        "itemType": "attachment",
        "contentType": "application/pdf",
        "title": "paper.pdf",
        "parentItem": "PARENT",
    }
    attachment = ZoteroAttachment.model_validate(data)
    service, _ = _make_service(
        [item],
        keys={"PARENT": "doe2024paper"},
        attachments=[attachment],
        pdf_dir=pdfs,
        zotero_storage_dir=storage,
    )
    result = service.import_all()
    assert result.pdfs_imported == 1
    imported = list(pdfs.glob("*.pdf"))
    assert len(imported) == 1
    assert imported[0].read_bytes() == b"%PDF-1.4 stored"
