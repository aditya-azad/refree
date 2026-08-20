import uuid
from datetime import UTC, datetime

from sqlalchemy import JSON, Column, DateTime
from sqlmodel import Field, SQLModel

from app.common.types import UTCDatetime


class Reference(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    title: str = Field(nullable=False)
    authors: list[str] = Field(
        default_factory=list,
        sa_column=Column(JSON, nullable=False),
    )
    year: int | None = Field(default=None, nullable=True)
    citation_key: str = Field(index=True, unique=True, nullable=False)
    doi: str | None = Field(default=None, nullable=True)
    url: str | None = Field(default=None, nullable=True)
    publication_title: str | None = Field(default=None, nullable=True)
    publisher: str | None = Field(default=None, nullable=True)
    volume: str | None = Field(default=None, nullable=True)
    issue: str | None = Field(default=None, nullable=True)
    pages: str | None = Field(default=None, nullable=True)
    language: str | None = Field(default=None, nullable=True)
    abstract_note: str | None = Field(default=None, nullable=True)
    item_type: str | None = Field(default=None, nullable=True)
    pdf_path: str | None = Field(default=None, nullable=True)
    created_at: UTCDatetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: UTCDatetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            onupdate=lambda: datetime.now(UTC),
        ),
    )
