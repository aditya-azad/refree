from collections.abc import Iterator
from pathlib import Path

import pymupdf
import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

import app.references.schemas as reference_schemas
from app.extraction.extractor import PdfTextExtractor
from app.extraction.repository import ExtractionRepository
from app.extraction.service import ExtractionService
from app.extraction.vector_store import VectorStore, build_vector_engine
from app.pdf_store.service import PdfStore
from app.references.repository import ReferencesRepository
from app.references.schemas import ReferenceCreate
from app.references.service import ReferencesService
from tests.fake_embedder import FakeEmbedder


def _make_pdf(path: Path, text: str) -> bytes:
    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((72, 72), text)
    document.save(path)
    document.close()
    return path.read_bytes()


@pytest.fixture()
def service(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[ExtractionService]:
    monkeypatch.setattr(reference_schemas, "PDF_DIR", tmp_path)
    session_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(session_engine)
    vector_engine = build_vector_engine("sqlite://", in_memory=True)
    session = Session(session_engine)
    references = ReferencesService(
        ReferencesRepository(session), PdfStore(tmp_path)
    )
    embedder = FakeEmbedder(dim=32)
    vector_store = VectorStore(embedder, engine=vector_engine)
    extraction = ExtractionService(
        ExtractionRepository(session),
        references,
        PdfTextExtractor(),
        embedder,
        vector_store,
    )
    yield extraction
    session.close()
    session_engine.dispose()
    vector_engine.dispose()


def _create(
    service: ReferencesService,
    title: str,
    *,
    abstract: str | None = None,
    citation_key: str | None = None,
) -> object:
    fields: dict[str, object] = {
        "title": title,
        "authors": ["Jane Doe"],
        "year": 2024,
    }
    if abstract is not None:
        fields["abstract_note"] = abstract
    if citation_key is not None:
        fields["citation_key"] = citation_key
    return service.create_reference(ReferenceCreate(**fields))  # type: ignore[arg-type]


def _attach_pdf(
    service: ReferencesService, reference_id: object, tmp_path: Path, text: str
) -> None:
    pdf_path = tmp_path / "paper.pdf"
    service.attach_pdf(reference_id, _make_pdf(pdf_path, text))  # type: ignore[arg-type]


def test_get_pdf_text_extracts_and_caches(
    service: ExtractionService, tmp_path: Path
) -> None:
    references = service._references
    ref = _create(references, "Deep Learning", citation_key="doe2024deep")
    _attach_pdf(references, ref.id, tmp_path, "Convolutional neural networks.")

    text = service.get_pdf_text(ref.id)
    assert text is not None
    assert "Convolutional neural networks" in text

    summary = service.get_content_summary(ref.id)
    assert summary is not None
    assert summary.char_count > 0

    text_again = service.get_pdf_text(ref.id)
    assert text_again == text


def test_get_pdf_text_re_extracts_when_pdf_changes(
    service: ExtractionService, tmp_path: Path
) -> None:
    references = service._references
    ref = _create(references, "Deep Learning", citation_key="doe2024deep")
    _attach_pdf(references, ref.id, tmp_path, "First version text.")

    first = service.get_pdf_text(ref.id)
    assert "First version" in first

    _attach_pdf(references, ref.id, tmp_path, "Second version text.")
    second = service.get_pdf_text(ref.id)
    assert "Second version" in second
    assert "First version" not in second


def test_get_pdf_text_none_when_no_pdf(
    service: ExtractionService,
) -> None:
    references = service._references
    ref = _create(references, "No PDF Paper", citation_key="doe2024nopdf")
    assert service.get_pdf_text(ref.id) is None


def test_keyword_search_finds_in_contents(
    service: ExtractionService, tmp_path: Path
) -> None:
    references = service._references
    ref = _create(references, "A Paper", citation_key="doe2024a")
    _attach_pdf(references, ref.id, tmp_path, "Transformers attention mechanism.")
    service.get_pdf_text(ref.id)

    hits = service.keyword_search("transformers")
    assert len(hits) == 1
    assert hits[0].citation_key == "doe2024a"
    assert "transformers" in hits[0].snippet.lower()


def test_keyword_search_finds_in_title_and_abstract(
    service: ExtractionService,
) -> None:
    references = service._references
    _create(
        references,
        "Graph Neural Networks",
        abstract="message passing on graphs",
        citation_key="doe2024gnn",
    )
    title_hits = service.keyword_search("graph")
    assert len(title_hits) == 1
    abstract_hits = service.keyword_search("message")
    assert len(abstract_hits) == 1


def test_keyword_search_requires_all_tokens(
    service: ExtractionService, tmp_path: Path
) -> None:
    references = service._references
    ref = _create(references, "Cat", citation_key="doe2024cat")
    _attach_pdf(references, ref.id, tmp_path, "feline animal")
    service.get_pdf_text(ref.id)
    assert service.keyword_search("cat quantum") == []


def test_semantic_search_ranks_relevant_first(
    service: ExtractionService, tmp_path: Path
) -> None:
    references = service._references
    relevant = _create(
        references,
        "Neural Networks",
        abstract="deep learning neural networks",
        citation_key="doe2024nn",
    )
    other = _create(
        references,
        "Cooking Recipes",
        abstract="soups and stews",
        citation_key="doe2024cook",
    )
    service.ensure_indexed(relevant.id)
    service.ensure_indexed(other.id)

    hits = service.semantic_search("neural networks learning")
    assert hits
    assert hits[0].citation_key == "doe2024nn"


def test_ensure_indexed_removes_vector_when_pdf_removed(
    service: ExtractionService, tmp_path: Path
) -> None:
    references = service._references
    ref = _create(references, "Deep Learning", citation_key="doe2024deep")
    _attach_pdf(references, ref.id, tmp_path, "some text")
    service.ensure_indexed(ref.id)
    assert service._vector_store.count() == 1

    references.delete_reference(ref.id)
    assert service._vector_store.count() == 1

    service.semantic_search("deep")
    stats = service.index_pending(batch_size=100)
    assert stats.completed_scans >= 1
    assert service._vector_store.count() == 0


def test_index_pending_processes_and_advances_watermark(
    service: ExtractionService, tmp_path: Path
) -> None:
    references = service._references
    ref = _create(references, "A", citation_key="doe2024a")
    _attach_pdf(references, ref.id, tmp_path, "indexed contents")
    _create(references, "B", citation_key="doe2024b")

    stats = service.index_pending(batch_size=100)
    assert stats.scanned == 2
    assert stats.embedded == 2
    assert stats.completed_scans >= 1
    assert service._vector_store.count() == 2


def test_search_returns_both_semantic_and_keyword(
    service: ExtractionService, tmp_path: Path
) -> None:
    references = service._references
    ref = _create(
        references,
        "Attention Is All You Need",
        abstract="transformer architecture",
        citation_key="vaswani2017attention",
    )
    _attach_pdf(references, ref.id, tmp_path, "self-attention layers")
    service.ensure_indexed(ref.id)

    result = service.search("attention")
    assert result.query == "attention"
    assert any(h.citation_key == "vaswani2017attention" for h in result.keyword)
    assert any(
        h.citation_key == "vaswani2017attention" for h in result.semantic
    )