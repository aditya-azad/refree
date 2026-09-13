from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from that_depends.providers import container_context
from that_depends.providers.context_resources import ContextScopes

from app.common.errors import DatabaseEntryNotFoundError
from app.extraction.container import ExtractionContainer
from app.extraction.schemas import PaperSearchResult
from app.extraction.service import ExtractionService
from app.mcp_server.schemas import BibEntry, PdfTextResult
from app.references.container import ReferencesContainer
from app.references.service import ReferencesService

_SEARCH_DESCRIPTION = (
    "Search the reference library over paper title, abstract, and full PDF "
    "contents. Runs both a semantic (embedding) search and a keyword "
    "(token) search for the same query and returns both ranked result sets."
)
_BIBTEX_DESCRIPTION = (
    "Return the BibTeX entry for a single paper identified by its citation "
    "key, ready to paste into a .bib file."
)
_PDF_TEXT_DESCRIPTION = (
    "Return the plain text extracted from a paper's PDF using mupdf. The "
    "extracted text is cached and re-extracted automatically when the PDF "
    "file changes."
)


def _resolve_services() -> tuple[ExtractionService, ReferencesService]:
    extraction = ExtractionContainer.extraction_service.resolve_sync()
    references = ReferencesContainer.references_service.resolve_sync()
    return extraction, references


def build_mcp_server() -> MCPServer:
    server = MCPServer(
        name="refree",
        instructions=(
            "Tools for searching the refree reference library (semantic + "
            "keyword over title, abstract, and PDF contents), fetching a "
            "paper's BibTeX entry, and extracting PDF text via mupdf."
        ),
    )

    @server.tool(description=_SEARCH_DESCRIPTION)
    def search_papers(query: str, limit: int = 20) -> PaperSearchResult:
        with container_context(scope=ContextScopes.REQUEST):
            extraction, _ = _resolve_services()
            return extraction.search(query, limit=limit)

    @server.tool(description=_BIBTEX_DESCRIPTION)
    def get_bibtex(citation_key: str) -> BibEntry:
        with container_context(scope=ContextScopes.REQUEST):
            _, references = _resolve_services()
            try:
                bibtex = references.export_bibtex_for_keys([citation_key])
            except DatabaseEntryNotFoundError as exc:
                raise ToolError(str(exc)) from exc
            return BibEntry(citation_key=citation_key, bibtex=bibtex)

    @server.tool(description=_PDF_TEXT_DESCRIPTION)
    def get_pdf_text(citation_key: str) -> PdfTextResult:
        with container_context(scope=ContextScopes.REQUEST):
            extraction, _ = _resolve_services()
            try:
                text = extraction.get_pdf_text_by_citation_key(citation_key)
            except DatabaseEntryNotFoundError as exc:
                raise ToolError(str(exc)) from exc
            if text is None:
                raise ToolError(
                    f"no PDF attached to citation key {citation_key!r}"
                )
            return PdfTextResult(
                citation_key=citation_key,
                text=text,
                char_count=len(text),
            )

    return server
