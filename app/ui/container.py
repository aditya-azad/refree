from pathlib import Path

from fastapi.templating import Jinja2Templates
from that_depends import BaseContainer
from that_depends.providers import Factory, Singleton

from app.common.config import PDF_DIR
from app.references.container import ReferencesContainer
from app.search.container import SearchContainer
from app.ui.service import UIService

_TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"


class UIContainer(BaseContainer):
    templates = Singleton(Jinja2Templates, directory=_TEMPLATES_DIR)
    ui_service = Factory(
        UIService,
        references_service=ReferencesContainer.references_service.cast,
        search_service=SearchContainer.search_service.cast,
        pdf_dir=PDF_DIR,
        templates=templates.cast,
    )
