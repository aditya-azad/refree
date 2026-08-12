from fastapi import FastAPI
from that_depends.providers import DIContextMiddleware
from that_depends.providers.context_resources import ContextScopes

from app.common.container import CommonContainer
from app.references.container import ReferencesContainer
from app.references.router import router as references_router
from app.zotero_browser_plugin.container import ZoteroBrowserPluginContainer
from app.zotero_browser_plugin.router import router as zotero_router

app = FastAPI()
app.add_middleware(DIContextMiddleware, scope=ContextScopes.REQUEST)

_CONTAINERS = (
    CommonContainer,
    ReferencesContainer,
    ZoteroBrowserPluginContainer,
)
# add routers
app.include_router(references_router)
app.include_router(zotero_router)


@app.get("/heartbeat")
async def heartbeat() -> dict[str, str]:
    return {"status": "ok"}
