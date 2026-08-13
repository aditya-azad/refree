import pytest

from app.references.citation_key import (
    CitationKeyGenerator,
    _base_citation_key,
)


def test_base_citation_key_handles_no_authors() -> None:
    key = _base_citation_key("Some Title", [], 2020)
    assert key == "anonSomeTitle2020"


def test_base_citation_key_handles_no_year() -> None:
    key = _base_citation_key("Some Title", ["Jane Doe"], None)
    assert key == "doeSomeTitle"


def test_base_citation_key_strips_filler_words_from_title() -> None:
    key = _base_citation_key(
        "The Art of Programming", ["Donald Knuth", "Bob"], 1968
    )
    assert key == "knuthArtProgramming1968"


def test_base_citation_key_falls_back_to_ref_for_empty_title() -> None:
    key = _base_citation_key("", ["Jane Doe"], 2020)
    assert key == "doeRef2020"


def test_generate_basic_key_from_author_year_title() -> None:
    key = CitationKeyGenerator.generate(
        "Deep Learning", ["Ian Goodfellow", "Yoshua Bengio"], 2016, set()
    )
    assert key == "goodfellowDeepLearning2016"


def test_generate_disambiguates_with_suffix_on_collision() -> None:
    base = _base_citation_key("Deep Learning", ["Ian Goodfellow"], 2016)
    taken = {base}
    key = CitationKeyGenerator.generate(
        "Deep Learning", ["Ian Goodfellow"], 2016, taken
    )
    assert key == base + "a"


def test_generate_skips_multiple_taken_suffixes() -> None:
    base = _base_citation_key("Deep Learning", ["Ian Goodfellow"], 2016)
    taken = {base, base + "a", base + "b", base + "c"}
    key = CitationKeyGenerator.generate(
        "Deep Learning", ["Ian Goodfellow"], 2016, taken
    )
    assert key == base + "d"


def test_generate_exhausts_suffix_space_raises() -> None:
    base = _base_citation_key("Deep Learning", ["Ian Goodfellow"], 2016)
    letters = "abcdefghijklmnopqrstuvwxyz"
    taken = {base}
    taken.update(base + c for c in letters)
    for first in letters:
        for second in letters:
            taken.add(base + first + second)
    with pytest.raises(RuntimeError, match="exhausted citation key space"):
        CitationKeyGenerator.generate(
            "Deep Learning", ["Ian Goodfellow"], 2016, taken
        )


def test_resolve_explicit_key_stores_verbatim_when_free() -> None:
    key = CitationKeyGenerator.resolve_explicit("goodfellow2016deep", set())
    assert key == "goodfellow2016deep"


def test_resolve_explicit_key_appends_suffix_on_collision() -> None:
    key = CitationKeyGenerator.resolve_explicit("dupKey", {"dupKey"})
    assert key == "dupKeya"


def test_resolve_explicit_key_skips_multiple_taken() -> None:
    key = CitationKeyGenerator.resolve_explicit(
        "dupKey", {"dupKey", "dupKeya", "dupKeyb"}
    )
    assert key == "dupKeyc"


def test_resolve_explicit_exhausts_suffix_space_raises() -> None:
    letters = "abcdefghijklmnopqrstuvwxyz"
    taken = {"dupKey"}
    taken.update("dupKey" + c for c in letters)
    for first in letters:
        for second in letters:
            taken.add("dupKey" + first + second)
    with pytest.raises(RuntimeError, match="exhausted citation key space"):
        CitationKeyGenerator.resolve_explicit("dupKey", taken)


def test_generate_handles_no_authors() -> None:
    key = CitationKeyGenerator.generate("Untitled Work", [], 2021, set())
    assert key == "anonUntitledWork2021"


def test_generate_handles_no_year() -> None:
    key = CitationKeyGenerator.generate(
        "Untitled Work", ["Jane Doe"], None, set()
    )
    assert key == "doeUntitledWork"
