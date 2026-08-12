from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.common.types import UTCDatetime


class ItemBase(BaseModel):
    name: str
    description: str | None = None


class ItemCreate(ItemBase):
    pass


class ItemUpdate(BaseModel):
    name: str | None = None
    description: str | None = None


class ItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: str | None = None
    created_at: UTCDatetime
    updated_at: UTCDatetime
