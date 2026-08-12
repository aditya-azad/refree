from pathlib import Path
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.common.types import DOI, URL
from app.zotero.schemas import ZoteroCreator


class ConnectorItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")

    item_id: str | None = Field(default=None, alias="id")
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
    key: str | None = None
    citation_key: str | None = None

    @field_validator("doi", "url", mode="before")
    @classmethod
    def _empty_to_none(cls, value: object) -> object:
        if value == "":
            return None
        return value


class ConnectorSaveItemsRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    items: list[ConnectorItem]
    session_id: str = Field(alias="sessionID")
    uri: str | None = None


class SaveItemsResponse(BaseModel):
    items: list[ConnectorItem]


class SavedReference(BaseModel):
    reference_id: UUID


class ConnectorAttachmentMetadata(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")
    title: str = ""
    parent_item_id: str | None = Field(default=None, alias="parentItemID")
    url: str | None = None
    content_type: str | None = Field(default=None, alias="contentType")


class PdfAttachment(BaseModel):
    reference_id: UUID
    path: Path
