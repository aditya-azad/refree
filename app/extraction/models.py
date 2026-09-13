import uuid
from datetime import UTC, datetime

from sqlalchemy import Column, DateTime
from sqlmodel import Field, SQLModel

from app.common.types import UTCDatetime


class PdfContent(SQLModel, table=True):
    reference_id: uuid.UUID = Field(
        foreign_key="reference.id", primary_key=True
    )
    content_hash: str = Field(nullable=False, index=True)
    text: str = Field(nullable=False)
    char_count: int = Field(default=0, nullable=False)
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


class ExtractionWatermark(SQLModel, table=True):
    name: str = Field(primary_key=True, default="extraction")
    cursor_reference_id: uuid.UUID | None = Field(default=None, nullable=True)
    completed_scans: int = Field(default=0, nullable=False)
    updated_at: UTCDatetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            onupdate=lambda: datetime.now(UTC),
        ),
    )
