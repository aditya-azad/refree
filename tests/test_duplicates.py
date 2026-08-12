import uuid

from app.references.duplicates import DuplicateDetector
from app.references.models import Reference


def _ref(**overrides: object) -> Reference:
    fields: dict[str, object] = {
        "id": uuid.uuid4(),
        "title": "Untitled",
        "authors": ["Jane Doe"],
        "year": 2020,
        "citation_key": "doe2020untitled",
        "doi": None,
        "url": None,
        "publication_title": None,
        "publisher": None,
        "volume": None,
        "issue": None,
        "pages": None,
        "language": None,
        "abstract_note": None,
        "pdf_path": None,
    }
    fields.update(overrides)
    return Reference(**fields)  # type: ignore[arg-type]


def test_find_groups_empty_when_no_references() -> None:
    assert DuplicateDetector.find_groups([]) == []


def test_find_groups_single_reference_no_duplicates() -> None:
    assert DuplicateDetector.find_groups([_ref()]) == []


def test_find_groups_no_duplicates() -> None:
    refs = [
        _ref(title="Paper A", citation_key="a", doi="10.1/a"),
        _ref(title="Paper B", citation_key="b", doi="10.1/b"),
    ]
    assert DuplicateDetector.find_groups(refs) == []


def test_find_groups_by_doi_case_insensitive() -> None:
    a = _ref(title="Paper A", citation_key="a", doi="10.1000/ABC")
    b = _ref(title="Paper B", citation_key="b", doi="10.1000/abc")
    groups = DuplicateDetector.find_groups([a, b])
    assert len(groups) == 1
    assert len(groups[0]) == 2


def test_find_groups_by_title_and_year() -> None:
    a = _ref(title="Deep Learning", citation_key="a", authors=["Ian Goodfellow"], year=2016, doi="10.1/a")
    b = _ref(title="Deep Learning", citation_key="b", authors=["Yoshua Bengio"], year=2016, doi="10.1/b")
    groups = DuplicateDetector.find_groups([a, b])
    assert len(groups) == 1
    assert len(groups[0]) == 2


def test_find_groups_by_title_and_author() -> None:
    a = _ref(title="Deep Learning", citation_key="a", authors=["Ian Goodfellow"], year=None, doi="10.1/a")
    b = _ref(title="Deep Learning", citation_key="b", authors=["Ian Goodfellow"], year=None, doi="10.1/b")
    groups = DuplicateDetector.find_groups([a, b])
    assert len(groups) == 1
    assert len(groups[0]) == 2


def test_find_groups_transitive_clustering() -> None:
    a = _ref(title="Shared Title", citation_key="a", authors=["Ian Goodfellow"], year=2020, doi="10.1/abc")
    b = _ref(title="Shared Title", citation_key="b", authors=["Ian Goodfellow"], year=2020, doi="10.1/xyz")
    c = _ref(title="Other Title", citation_key="c", authors=["Ian Goodfellow"], year=2020, doi="10.1/xyz")
    groups = DuplicateDetector.find_groups([a, b, c])
    assert len(groups) == 1
    assert len(groups[0]) == 3


def test_find_groups_returns_reference_objects() -> None:
    a = _ref(title="Paper", citation_key="a", doi="10.1/abc")
    b = _ref(title="Paper", citation_key="b", doi="10.1/abc")
    groups = DuplicateDetector.find_groups([a, b])
    assert all(isinstance(r, Reference) for r in groups[0])


def test_find_groups_members_sorted_by_title() -> None:
    a = _ref(title="Zeta Paper", citation_key="a", doi="10.1/abc")
    b = _ref(title="Alpha Paper", citation_key="b", doi="10.1/abc")
    groups = DuplicateDetector.find_groups([a, b])
    titles = [r.title for r in groups[0]]
    assert titles == ["Alpha Paper", "Zeta Paper"]


def test_find_groups_groups_sorted_by_first_title() -> None:
    a1 = _ref(title="Zeta Paper", citation_key="a1", doi="10.1/z")
    a2 = _ref(title="Zeta Paper", citation_key="a2", doi="10.1/z")
    b1 = _ref(title="Alpha Paper", citation_key="b1", doi="10.1/a")
    b2 = _ref(title="Alpha Paper", citation_key="b2", doi="10.1/a")
    groups = DuplicateDetector.find_groups([a1, a2, b1, b2])
    assert [g[0].title for g in groups] == ["Alpha Paper", "Zeta Paper"]


def test_duplicate_keys_empty_for_reference_without_doi_or_title() -> None:
    ref = _ref(title="!!!", doi=None, authors=[], year=None)
    assert DuplicateDetector._duplicate_keys(ref) == []


def test_duplicate_keys_doi_lowercase() -> None:
    ref = _ref(doi="10.1000/ABC")
    keys = DuplicateDetector._duplicate_keys(ref)
    assert "doi:10.1000/abc" in keys


def test_duplicate_keys_title_year_and_author() -> None:
    ref = _ref(title="Deep Learning 2016!", authors=["Ian Goodfellow"], year=2016)
    keys = DuplicateDetector._duplicate_keys(ref)
    assert "ty:deeplearning2016|2016" in keys
    assert "ta:deeplearning2016|goodfellow" in keys


def test_normalize_title_strips_non_alphanumeric() -> None:
    from app.references.duplicates import normalize_title

    assert normalize_title("Deep Learning 2016!") == "deeplearning2016"
    assert normalize_title("A,B;C") == "abc"
    assert normalize_title("") == ""
