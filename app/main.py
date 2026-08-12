from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from that_depends.providers import DIContextMiddleware
from that_depends.providers.context_resources import ContextScopes

from app.common.container import CommonContainer
from app.common.database import create_db_and_tables
from app.pdf_store.container import PdfStoreContainer
from app.references.container import ReferencesContainer
from app.references.router import router as references_router
from app.search.container import SearchContainer
from app.ui.container import UIContainer
from app.ui.router import router as ui_router
from app.zotero.container import ZoteroContainer
from app.zotero_browser_plugin.container import (
    ZoteroBrowserPluginContainer,
)
from app.zotero_browser_plugin.router import router as zotero_router


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None]:
    create_db_and_tables()
    yield


app = FastAPI(lifespan=lifespan)
app.add_middleware(DIContextMiddleware, scope=ContextScopes.REQUEST)

_CONTAINERS = (
    CommonContainer,
    PdfStoreContainer,
    ReferencesContainer,
    SearchContainer,
    UIContainer,
    ZoteroContainer,
    ZoteroBrowserPluginContainer,
)
# add routers
app.include_router(references_router)
app.include_router(zotero_router)
app.include_router(ui_router)


@app.get("/heartbeat")
async def heartbeat() -> dict[str, str]:
    return {"status": "ok"}
