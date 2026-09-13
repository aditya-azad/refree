from pathlib import Path

import pymupdf
import pytest

from app.extraction.extractor import PdfTextExtractor


def _make_pdf(path: Path, text: str) -> None:
    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((72, 72), text)
    document.save(path)
    document.close()


def test_extract_returns_page_text(tmp_path: Path) -> None:
    pdf_path = tmp_path / "doc.pdf"
    _make_pdf(pdf_path, "Hello mupdf world.")
    extractor = PdfTextExtractor()
    text = extractor.extract(pdf_path)
    assert "Hello mupdf world" in text


def test_extract_handles_multi_page(tmp_path: Path) -> None:
    pdf_path = tmp_path / "multi.pdf"
    document = pymupdf.open()
    document.new_page().insert_text((72, 72), "Page one text.")
    document.new_page().insert_text((72, 72), "Page two text.")
    document.save(pdf_path)
    document.close()
    text = PdfTextExtractor().extract(pdf_path)
    assert "Page one text" in text
    assert "Page two text" in text