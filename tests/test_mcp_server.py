import asyncio
import json
from collections.abc import Iterator
from pathlib import Path

import pymupdf
import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

import app.references.schemas as reference_schemas
from app.extraction.container import ExtractionContainer
from app.extraction.extractor import PdfTextExtractor
from app.extraction.repository import ExtractionRepository
from app.extraction.service import ExtractionService
from app.extraction.vector_store import VectorStore, build_vector_engine
from app.mcp_server.server import build_mcp_server
from app.pdf_store.service import PdfStore
from app.references.container import ReferencesContainer
from app.references.repository import ReferencesRepository
from app.references.schemas import ReferenceCreate
from app.references.service import ReferencesService
from tests.fake_embedder import FakeEmbedder


def _make_pdf(path: Path, text: str) -> bytes:
    document = pymupdf.open()
    document.new_page().insert_text((72, 72), text)
    document.save(path)
    document.close()
    return path.read_bytes()


@pytest.fixture()
def server(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[object]:
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
    ReferencesContainer.references_service.override_sync(references)
    ExtractionContainer.extraction_service.override_sync(extraction)
    yield build_mcp_server()
    ReferencesContainer.references_service.reset_override_sync()
    ExtractionContainer.extraction_service.reset_override_sync()
    session.close()
    session_engine.dispose()
    vector_engine.dispose()


def _create_reference(
    references: ReferencesService,
    title: str,
    citation_key: str,
    abstract: str | None = None,
) -> object:
    fields: dict[str, object] = {
        "title": title,
        "authors": ["Jane Doe"],
        "year": 2024,
        "citation_key": citation_key,
    }
    if abstract is not None:
        fields["abstract_note"] = abstract
    return references.create_reference(ReferenceCreate(**fields))  # type: ignore[arg-type]


def _call(server: object, name: str, args: dict[str, object]) -> object:
    return asyncio.run(server.call_tool(name, args))  # type: ignore[attr-defined]


def _payload(result: object) -> dict[str, object]:
    assert not result.is_error  # type: ignore[attr-defined]
    return json.loads(result.content[0].text)  # type: ignore[attr-defined]


def test_search_papers_runs_both_semantic_and_keyword(
    server: object, tmp_path: Path
) -> None:
    references = ReferencesContainer.references_service.resolve_sync()
    ref = _create_reference(
        references,
        "Attention Is All You Need",
        "vaswani2017attention",
        abstract="transformer architecture",
    )
    references.attach_pdf(
        ref.id, _make_pdf(tmp_path / "p.pdf", "self-attention layers")  # type: ignore[arg-type]
    )
    ExtractionContainer.extraction_service.resolve_sync().ensure_indexed(
        ref.id
    )

    result = _call(
        server, "search_papers", {"query": "attention", "limit": 5}
    )
    payload = _payload(result)
    assert payload["query"] == "attention"
    assert any(
        h["citation_key"] == "vaswani2017attention"
        for h in payload["semantic"]
    )
    assert any(
        h["citation_key"] == "vaswani2017attention"
        for h in payload["keyword"]
    )


def test_get_bibtex_returns_entry_for_citation_key(
    server: object,
) -> None:
    references = ReferencesContainer.references_service.resolve_sync()
    _create_reference(
        references,
        "Deep Learning",
        "doe2024deep",
        abstract="neural networks",
    )

    payload = _payload(
        _call(server, "get_bibtex", {"citation_key": "doe2024deep"})
    )
    assert payload["citation_key"] == "doe2024deep"
    assert "doe2024deep" in str(payload["bibtex"])
    assert str(payload["bibtex"]).lstrip().startswith("@")


def test_get_bibtex_missing_key_is_error(server: object) -> None:
    from mcp.server.mcpserver.exceptions import ToolError

    with pytest.raises(ToolError):
        _call(server, "get_bibtex", {"citation_key": "nope9999"})


def test_get_pdf_text_returns_extracted_text(
    server: object, tmp_path: Path
) -> None:
    references = ReferencesContainer.references_service.resolve_sync()
    ref = _create_reference(
        references, "A Paper", "doe2024a", abstract="some abstract"
    )
    references.attach_pdf(
        ref.id, _make_pdf(tmp_path / "p.pdf", "Extracted mupdf text.")  # type: ignore[arg-type]
    )

    payload = _payload(
        _call(server, "get_pdf_text", {"citation_key": "doe2024a"})
    )
    assert payload["citation_key"] == "doe2024a"
    assert "Extracted mupdf text" in str(payload["text"])
    assert int(payload["char_count"]) > 0


def test_get_pdf_text_without_pdf_is_error(server: object) -> None:
    from mcp.server.mcpserver.exceptions import ToolError

    references = ReferencesContainer.references_service.resolve_sync()
    _create_reference(references, "No PDF", "doe2024nopdf")
    with pytest.raises(ToolError):
        _call(server, "get_pdf_text", {"citation_key": "doe2024nopdf"})