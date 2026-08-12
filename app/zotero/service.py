import re

from app.references.schemas import ReferenceCreate
from app.zotero.schemas import ZoteroItemLike


def extract_year(date: str | None) -> str:
    if not date:
        return ""
    match = re.search(r"\d{4}", date)
    return match.group(0) if match else ""


def first_author_last_name(item: ZoteroItemLike) -> str:
    for creator in item.creators:
        if creator.creator_type != "author":
            continue
        if creator.last_name:
            return creator.last_name
        if creator.name:
            return creator.name
        return ""
    return ""


def authors_from_creators(item: ZoteroItemLike) -> list[str]:
    authors: list[str] = []
    for creator in item.creators:
        if creator.creator_type != "author":
            continue
        if creator.last_name and creator.first_name:
            authors.append(f"{creator.first_name} {creator.last_name}")
        elif creator.last_name:
            authors.append(creator.last_name)
        elif creator.name:
            authors.append(creator.name)
    return authors


def year_from_item(item: ZoteroItemLike) -> int | None:
    year_str = extract_year(item.date)
    return int(year_str) if year_str else None


def to_reference_create(item: ZoteroItemLike) -> ReferenceCreate:
    return ReferenceCreate(
        title=item.title,
        authors=authors_from_creators(item),
        year=year_from_item(item),
        doi=item.doi,
        url=item.url,
        publication_title=item.publication_title,
        publisher=item.publisher,
        volume=item.volume,
        issue=item.issue,
        pages=item.pages,
        language=item.language,
        abstract_note=item.abstract_note,
        citation_key=item.citation_key,
    )
