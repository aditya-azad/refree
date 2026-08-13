from datetime import UTC, datetime
from uuid import uuid4

from app.common.config import PDF_DIR
from app.references.schemas import ReferenceRead


def _read(**overrides: object) -> ReferenceRead:
    fields: dict[str, object] = {
        "id": uuid4(),
        "title": "Some Title",
        "authors": ["Jane Doe"],
        "year": 2024,
        "citation_key": "doe2024some",
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
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
    }
    fields.update(overrides)
    return ReferenceRead(**fields)  # type: ignore[arg-type]


def test_relative_pdf_path_resolved_against_pdf_dir() -> None:
    ref = _read(pdf_path="Smith2024Example.pdf")
    assert ref.pdf_path == str(PDF_DIR / "Smith2024Example.pdf")


def test_absolute_pdf_path_kept_unchanged() -> None:
    abs_path = "/home/user/papers/Smith2024Example.pdf"
    ref = _read(pdf_path=abs_path)
    assert ref.pdf_path == abs_path


def test_none_pdf_path_stays_none() -> None:
    ref = _read(pdf_path=None)
    assert ref.pdf_path is None
    assert ref.has_pdf is False


def test_empty_pdf_path_becomes_none() -> None:
    ref = _read(pdf_path="")
    assert ref.pdf_path is None
    assert ref.has_pdf is False


def test_has_pdf_true_when_relative_path_resolved() -> None:
    ref = _read(pdf_path="Smith2024Example.pdf")
    assert ref.has_pdf is True
