import re
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.references.bibtex import BibTeXWriter
from app.references.schemas import ReferenceRead


def _ref(**overrides: object) -> ReferenceRead:
    now = datetime.now(UTC)
    fields: dict[str, object] = {
        "id": uuid4(),
        "title": "Deep Learning",
        "authors": ["Ian Goodfellow", "Yoshua Bengio"],
        "year": 2016,
        "citation_key": "goodfellow2016deep",
        "doi": None,
        "url": None,
        "publication_title": None,
        "publisher": None,
        "volume": None,
        "issue": None,
        "pages": None,
        "language": None,
        "abstract_note": None,
        "item_type": None,
        "pdf_path": None,
        "created_at": now,
        "updated_at": now,
    }
    fields.update(overrides)
    return ReferenceRead(**fields)  # type: ignore[arg-type]


def _has_field(entry: str, name: str) -> bool:
    return re.search(rf"^\s*{re.escape(name)}\s*=", entry, re.MULTILINE) is not None


def _field_value(entry: str, name: str) -> str | None:
    m = re.search(
        rf"^\s*{re.escape(name)}\s*=\s*\{{(.*?)\}},?\s*$",
        entry,
        re.MULTILINE,
    )
    return m.group(1) if m else None


def _field_names(entry: str) -> list[str]:
    return [
        m.group(1)
        for m in re.finditer(r"^\s*(\w+)\s*=", entry, re.MULTILINE)
    ]


@pytest.mark.parametrize(
    ("item_type", "entry_type"),
    [
        ("journalArticle", "@article"),
        ("conferencePaper", "@inproceedings"),
        ("bookSection", "@incollection"),
        ("book", "@book"),
        ("thesis", "@phdthesis"),
        ("preprint", "@misc"),
        ("report", "@techreport"),
        ("dataset", "@misc"),
        ("standard", "@misc"),
        (None, "@misc"),
        ("unknownType", "@misc"),
    ],
)
def test_item_type_maps_to_entry_type(
    item_type: str | None, entry_type: str
) -> None:
    entry = BibTeXWriter.format_entry(_ref(item_type=item_type))
    assert entry.startswith(f"{entry_type}{{")


def test_authors_joined_with_and_separator() -> None:
    entry = BibTeXWriter.format_entry(
        _ref(authors=["Ian Goodfellow", "Yoshua Bengio", "Aaron Courville"])
    )
    assert _field_value(entry, "author") == (
        "Ian Goodfellow and Yoshua Bengio and Aaron Courville"
    )


def test_empty_authors_omits_author_field() -> None:
    entry = BibTeXWriter.format_entry(_ref(authors=[]))
    assert not _has_field(entry, "author")


def test_latex_special_chars_escaped_in_title() -> None:
    entry = BibTeXWriter.format_entry(_ref(title="a&b%c$d#e_f{g}h~i^j"))
    assert _field_value(entry, "title") == r"a\&b\%c\$d\#e\_f\{g\}h\~i\^j"


def test_backslash_escaped_in_title() -> None:
    entry = BibTeXWriter.format_entry(_ref(title="a\\b"))
    assert _field_value(entry, "title") == "a\\\\b"


def test_doi_and_url_not_escaped() -> None:
    entry = BibTeXWriter.format_entry(
        _ref(doi="10.1234/example", url="https://example.com/path?a=1&b=2")
    )
    assert _field_value(entry, "doi") == "10.1234/example"
    assert _field_value(entry, "url") == "https://example.com/path?a=1&b=2"
    assert r"\&" not in entry


@pytest.mark.parametrize(
    ("item_type", "field"),
    [
        ("journalArticle", "journal"),
        ("conferencePaper", "booktitle"),
        ("bookSection", "booktitle"),
        ("book", "note"),
        (None, "note"),
        ("preprint", "note"),
    ],
)
def test_publication_title_maps_to_contextual_field(
    item_type: str | None, field: str
) -> None:
    entry = BibTeXWriter.format_entry(
        _ref(item_type=item_type, publication_title="Venue")
    )
    assert _has_field(entry, field)


def test_journal_article_publication_title_only_to_journal() -> None:
    entry = BibTeXWriter.format_entry(
        _ref(item_type="journalArticle", publication_title="Nature")
    )
    assert _has_field(entry, "journal")
    assert not _has_field(entry, "booktitle")
    assert not _has_field(entry, "note")


@pytest.mark.parametrize(
    ("pages", "expected"),
    [
        ("1-10", "1--10"),
        ("1 - 10", "1--10"),
        ("1\u201310", "1--10"),
        ("1\u201410", "1--10"),
        ("10", "10"),
    ],
)
def test_pages_normalized(pages: str, expected: str) -> None:
    entry = BibTeXWriter.format_entry(_ref(pages=pages))
    assert _field_value(entry, "pages") == expected


def test_minimal_entry_has_only_title_field() -> None:
    entry = BibTeXWriter.format_entry(
        _ref(
            authors=[],
            year=None,
            citation_key="minimal2020",
            title="Minimal",
        )
    )
    assert entry.startswith("@misc{minimal2020,")
    assert _field_names(entry) == ["title"]
    assert _field_value(entry, "title") == "Minimal"
    assert entry.rstrip().endswith("}")


def test_citation_key_is_entry_key() -> None:
    entry = BibTeXWriter.format_entry(_ref(citation_key="goodfellow2016deep"))
    assert re.match(r"^@\w+\{goodfellow2016deep,", entry)


def test_format_bibliography_sorts_by_citation_key() -> None:
    refs = [
        _ref(citation_key="zebra2020"),
        _ref(citation_key="alpha2020"),
        _ref(citation_key="middle2020"),
    ]
    bib = BibTeXWriter.format_bibliography(refs)
    keys = re.findall(r"^@\w+\{([^,]+),", bib, re.MULTILINE)
    assert keys == ["alpha2020", "middle2020", "zebra2020"]


def test_entries_are_well_formed() -> None:
    refs = [
        _ref(
            citation_key="alpha2020",
            title="C++ & {GPU} ~100x",
            doi="10.1/x",
            url="https://x.org?a=1&b=2",
            pages="1-20",
            volume="42",
            issue="7",
            publisher="MIT Press",
            language="en",
            abstract_note="A & B summary",
            item_type="journalArticle",
            publication_title="Nature",
        ),
        _ref(
            citation_key="beta2020",
            title="Minimal",
            authors=[],
            year=None,
        ),
        _ref(citation_key="gamma2020", item_type="conferencePaper"),
    ]
    bib = BibTeXWriter.format_bibliography(refs)
    for entry in bib.split("\n\n"):
        assert re.match(r"^@\w+\{[^,]+,", entry), entry
        assert entry.count("{") == entry.count("}"), entry
