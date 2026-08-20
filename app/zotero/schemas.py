from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field


class ZoteroCreator(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")

    creator_type: str = Field(alias="creatorType")
    first_name: str | None = Field(default=None, alias="firstName")
    last_name: str | None = Field(default=None, alias="lastName")
    name: str | None = None


class ZoteroItemLike(Protocol):
    title: str
    creators: list[ZoteroCreator]
    date: str | None
    doi: str | None
    url: str | None
    publication_title: str | None
    publisher: str | None
    volume: str | None
    issue: str | None
    pages: str | None
    language: str | None
    abstract_note: str | None
    citation_key: str | None
    item_type: str
