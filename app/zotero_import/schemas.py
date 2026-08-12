from pydantic import BaseModel, ConfigDict, Field, RootModel, field_validator

from app.common.types import DOI, URL
from app.zotero.schemas import ZoteroCreator


class ZoteroItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")

    item_key: str = Field(alias="key")
    item_type: str = Field(alias="itemType")
    title: str
    creators: list[ZoteroCreator] = []
    doi: DOI | None = Field(default=None, alias="DOI")
    url: URL | None = Field(default=None, alias="url")
    date: str | None = None
    publication_title: str | None = Field(
        default=None, alias="publicationTitle"
    )
    publisher: str | None = None
    volume: str | None = None
    issue: str | None = None
    pages: str | None = None
    language: str | None = None
    abstract_note: str | None = Field(default=None, alias="abstractNote")
    citation_key: str | None = None

    @field_validator("doi", "url", mode="before")
    @classmethod
    def _empty_to_none(cls, value: object) -> object:
        if value == "":
            return None
        return value


class ZoteroImportResult(BaseModel):
    imported: int = 0
    updated: int = 0
    skipped: int = 0
    pdfs_imported: int = 0
    pdfs_skipped: int = 0
    errors: list[str] = []


class CitationKeyResponse(RootModel[dict[str, str]]):
    root: dict[str, str] = {}


class ZoteroAttachment(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")

    item_key: str = Field(alias="key")
    parent_item_key: str | None = Field(default=None, alias="parentItem")
    content_type: str | None = Field(default=None, alias="contentType")
    title: str = ""
    path: str | None = None
