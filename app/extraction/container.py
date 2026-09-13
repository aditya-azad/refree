from that_depends import BaseContainer
from that_depends.providers import Factory, Singleton

from app.common.config import EMBEDDING_MODEL
from app.common.container import CommonContainer
from app.extraction.embedder import Embedder
from app.extraction.extractor import PdfTextExtractor
from app.extraction.repository import ExtractionRepository
from app.extraction.service import ExtractionService
from app.extraction.vector_store import VectorStore, vector_engine
from app.references.container import ReferencesContainer


class ExtractionContainer(BaseContainer):
    embedder = Singleton(Embedder, model_name=EMBEDDING_MODEL)
    pdf_text_extractor = Singleton(PdfTextExtractor)
    vector_store = Singleton(
        VectorStore, embedder=embedder.cast, engine=vector_engine
    )
    extraction_repository = Factory(
        ExtractionRepository, session=CommonContainer.session.cast
    )
    extraction_service = Factory(
        ExtractionService,
        repository=extraction_repository.cast,
        references_service=ReferencesContainer.references_service.cast,
        extractor=pdf_text_extractor.cast,
        embedder=embedder.cast,
        vector_store=vector_store.cast,
    )
