from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.common.types import (
    DOI,
    URL,
    Authors,
    ProperWhitespacedStr,
    UTCDatetime,
)


class ReferenceCreate(BaseModel):
    title: ProperWhitespacedStr
    authors: Authors = []
    year: int | None = None
    doi: DOI | None = None
    url: URL | None = None
    publication_title: ProperWhitespacedStr | None = None
    publisher: ProperWhitespacedStr | None = None
    volume: ProperWhitespacedStr | None = None
    issue: ProperWhitespacedStr | None = None
    pages: ProperWhitespacedStr | None = None
    language: ProperWhitespacedStr | None = None
    abstract_note: ProperWhitespacedStr | None = None
    citation_key: str | None = None


class ReferenceUpdate(BaseModel):
    title: ProperWhitespacedStr | None = None
    authors: Authors | None = None
    year: int | None = None
    doi: DOI | None = None
    url: URL | None = None
    publication_title: ProperWhitespacedStr | None = None
    publisher: ProperWhitespacedStr | None = None
    volume: ProperWhitespacedStr | None = None
    issue: ProperWhitespacedStr | None = None
    pages: ProperWhitespacedStr | None = None
    language: ProperWhitespacedStr | None = None
    abstract_note: ProperWhitespacedStr | None = None


class ReferenceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    authors: list[str]
    year: int | None
    citation_key: str
    doi: str | None
    url: str | None
    publication_title: str | None
    publisher: str | None
    volume: str | None
    issue: str | None
    pages: str | None
    language: str | None
    abstract_note: str | None
    pdf_path: str | None
    created_at: UTCDatetime
    updated_at: UTCDatetime


class DuplicateGroupRead(BaseModel):
    references: list[ReferenceRead]


class MergeRequest(BaseModel):
    reference_ids: list[UUID]
    survivor_id: UUID | None = None
    field_choices: dict[str, UUID] | None = None
