from pydantic import BaseModel

from app.references.schemas import ReferenceRead


class SearchPage(BaseModel):
    results: list[ReferenceRead]
    total: int
