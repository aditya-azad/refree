import re
from collections.abc import Iterator

_FILLER_WORDS = frozenset(
    {
        "a",
        "an",
        "the",
        "and",
        "or",
        "but",
        "of",
        "in",
        "on",
        "at",
        "to",
        "for",
        "with",
        "by",
        "from",
        "as",
        "is",
        "are",
        "be",
        "been",
        "this",
        "that",
        "these",
        "those",
        "it",
        "its",
        "de",
        "du",
        "la",
        "le",
        "el",
        "los",
        "las",
    }
)


def _first_author_last_name(authors: list[str]) -> str:
    if not authors:
        return ""
    parts = re.split(r"\s+", authors[0].strip())
    return parts[-1] if parts else ""


def _camel_case_word(word: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9]", "", word)
    if not cleaned:
        return ""
    return cleaned[0].upper() + cleaned[1:].lower()


def _short_title(title: str) -> str:
    picked: list[str] = []
    for word in re.split(r"\s+", title.strip()):
        if not word:
            continue
        if word.lower() in _FILLER_WORDS:
            continue
        camel = _camel_case_word(word)
        if camel:
            picked.append(camel)
        if len(picked) == 3:
            break
    return "".join(picked)


def _base_citation_key(title: str, authors: list[str], year: int | None) -> str:
    auth = re.sub(r"[^A-Za-z0-9]", "", _first_author_last_name(authors)).lower()
    if not auth:
        auth = "anon"
    short = _short_title(title)
    if not short:
        short = "Ref"
    yr = str(year) if year else ""
    return f"{auth}{short}{yr}"


def _disambiguation_suffixes() -> Iterator[str]:
    yield ""
    letters = "abcdefghijklmnopqrstuvwxyz"
    yield from letters
    for first in letters:
        for second in letters:
            yield first + second


class CitationKeyGenerator:
    @staticmethod
    def generate(
        title: str, authors: list[str], year: int | None, taken: set[str]
    ) -> str:
        base = _base_citation_key(title, authors, year)
        for suffix in _disambiguation_suffixes():
            candidate = base + suffix
            if candidate not in taken:
                return candidate
        msg = f"exhausted citation key space for base {base!r}"
        raise RuntimeError(msg)

    @staticmethod
    def resolve_explicit(key: str, taken: set[str]) -> str:
        for suffix in _disambiguation_suffixes():
            candidate = key + suffix
            if candidate not in taken:
                return candidate
        msg = f"exhausted citation key space for key {key!r}"
        raise RuntimeError(msg)
