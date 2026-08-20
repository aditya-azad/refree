import re
from collections.abc import Iterable

from app.references.schemas import ReferenceRead

_ITEM_TYPE_TO_BIBTEX: dict[str, str] = {
    "journalArticle": "@article",
    "conferencePaper": "@inproceedings",
    "bookSection": "@incollection",
    "book": "@book",
    "thesis": "@phdthesis",
    "preprint": "@misc",
    "report": "@techreport",
    "dataset": "@misc",
    "standard": "@misc",
}

_CANONICAL_FIELD_ORDER: list[str] = [
    "author",
    "title",
    "journal",
    "booktitle",
    "volume",
    "number",
    "pages",
    "publisher",
    "year",
    "doi",
    "url",
    "language",
    "abstract",
    "note",
]

_LATEX_SPECIAL: str = "&%$#_{}~^"


def _escape_latex(value: str) -> str:
    value = value.replace("\\", "\\\\")
    for ch in _LATEX_SPECIAL:
        value = value.replace(ch, "\\" + ch)
    return value


def _format_authors(authors: list[str]) -> str:
    return " and ".join(authors)


def _normalize_pages(pages: str) -> str:
    return re.sub(r"\s*[-\u2013\u2014]+\s*", "--", pages)


def _entry_type(item_type: str | None) -> str:
    if item_type is None:
        return "@misc"
    return _ITEM_TYPE_TO_BIBTEX.get(item_type, "@misc")


def _contextual_publication_field(entry_type: str) -> str:
    if entry_type == "@article":
        return "journal"
    if entry_type in ("@inproceedings", "@incollection", "@inbook"):
        return "booktitle"
    return "note"


class BibTeXWriter:
    @staticmethod
    def format_entry(ref: ReferenceRead) -> str:
        entry_type = _entry_type(ref.item_type)
        fields: dict[str, str] = {}
        if ref.authors:
            fields["author"] = _escape_latex(_format_authors(ref.authors))
        fields["title"] = _escape_latex(ref.title)
        if ref.publication_title is not None:
            fields[_contextual_publication_field(entry_type)] = _escape_latex(
                ref.publication_title
            )
        if ref.volume is not None:
            fields["volume"] = ref.volume
        if ref.issue is not None:
            fields["number"] = ref.issue
        if ref.pages is not None:
            fields["pages"] = _normalize_pages(ref.pages)
        if ref.publisher is not None:
            fields["publisher"] = _escape_latex(ref.publisher)
        if ref.year is not None:
            fields["year"] = str(ref.year)
        if ref.doi is not None:
            fields["doi"] = ref.doi
        if ref.url is not None:
            fields["url"] = ref.url
        if ref.language is not None:
            fields["language"] = ref.language
        if ref.abstract_note is not None:
            fields["abstract"] = _escape_latex(ref.abstract_note)

        ordered = [
            (name, fields[name])
            for name in _CANONICAL_FIELD_ORDER
            if name in fields
        ]
        width = max(len(name) for name, _ in ordered)
        lines: list[str] = [f"{entry_type}{{{ref.citation_key},"]
        for name, value in ordered:
            lines.append(f"  {name.ljust(width)} = {{{value}}},")
        lines.append("}")
        return "\n".join(lines)

    @staticmethod
    def format_bibliography(references: Iterable[ReferenceRead]) -> str:
        return "\n\n".join(
            BibTeXWriter.format_entry(r)
            for r in sorted(references, key=lambda r: r.citation_key)
        )
