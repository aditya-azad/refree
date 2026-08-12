from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.common.types import DOI, URL, Authors


class ZoteroItemCreate(BaseModel):
    zotero_key: str
    item_type: str
    title: str
    authors: Authors = []
    doi: DOI | None = None
    url: URL | None = None
    raw: dict[str, object] | None = None


class ZoteroItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    zotero_key: str
    item_id: UUID
