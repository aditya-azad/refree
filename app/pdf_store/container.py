from that_depends import BaseContainer
from that_depends.providers import Singleton

from app.common.config import PDF_DIR
from app.pdf_store.service import PdfStore


class PdfStoreContainer(BaseContainer):
    pdf_store = Singleton(PdfStore, pdf_dir=PDF_DIR)
