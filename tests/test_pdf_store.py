from pathlib import Path

from app.pdf_store.service import PdfStore


def test_store_creates_directory_and_writes_bytes(tmp_path: Path) -> None:
    pdf_dir = tmp_path / "pdfs"
    store = PdfStore(pdf_dir)
    relative = store.store("paper.pdf", b"%PDF-1.4 bytes")
    assert (pdf_dir / relative).read_bytes() == b"%PDF-1.4 bytes"
    assert pdf_dir.is_dir()


def test_store_deduplicates_filename_collisions(tmp_path: Path) -> None:
    store = PdfStore(tmp_path)
    first = store.store("paper.pdf", b"%PDF-1.4 one")
    second = store.store("paper.pdf", b"%PDF-1.4 two")
    assert first == Path("paper.pdf")
    assert second == Path("paper_1.pdf")
    assert (tmp_path / first).read_bytes() == b"%PDF-1.4 one"
    assert (tmp_path / second).read_bytes() == b"%PDF-1.4 two"


def test_store_returns_relative_path(tmp_path: Path) -> None:
    store = PdfStore(tmp_path / "pdfs")
    relative = store.store("deep.pdf", b"%PDF-1.4")
    assert not relative.is_absolute()
    assert relative == Path("deep.pdf")


def test_build_filename_sanitizes_unsafe_chars() -> None:
    name = PdfStore.build_filename("O'Brien", "2024", "A Paper: Title?")
    assert name == "O'Brien2024APaperTitle.pdf"
    assert PdfStore.build_filename("Lee", "2020", "C:\\/bad*file?") == "Lee2020Cbadfile.pdf"


def test_build_filename_falls_back_to_untitled() -> None:
    assert PdfStore.build_filename("", "", "") == "untitled.pdf"
    assert PdfStore.build_filename("   ", "   ", "   ") == "untitled.pdf"


def test_build_filename_appends_pdf_extension() -> None:
    assert PdfStore.build_filename("Doe", "2024", "Title").endswith(".pdf")
