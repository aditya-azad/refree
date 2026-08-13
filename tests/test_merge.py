import uuid

import pytest

from app.references.merge import MergeResolver
from app.references.models import Reference
from app.references.schemas import ReferenceRead


def _ref(**overrides: object) -> Reference:
    defaults: dict[str, object] = {
        "title": "Deep Learning",
        "authors": ["Ian Goodfellow"],
        "year": 2016,
        "citation_key": "key",
    }
    defaults.update(overrides)
    return Reference(**defaults)  # type: ignore[arg-type]


def _read(ref: Reference) -> ReferenceRead:
    return ReferenceRead.model_validate(ref)


def test_resolve_picks_most_complete_as_survivor() -> None:
    sparse = _ref(citation_key="a", doi=None, url=None, publisher=None)
    full = _ref(
        citation_key="b",
        doi="10.1000/xyz",
        url="https://example.com",
        publisher="MIT Press",
    )
    result = MergeResolver.resolve([sparse, full])
    assert result.survivor.id == full.id


def test_resolve_with_explicit_survivor_id() -> None:
    sparse = _ref(citation_key="a", doi=None)
    full = _ref(citation_key="b", doi="10.1000/xyz")
    result = MergeResolver.resolve([sparse, full], survivor_id=sparse.id)
    assert result.survivor.id == sparse.id


def test_resolve_survivor_not_in_members_raises() -> None:
    a = _ref(citation_key="a")
    b = _ref(citation_key="b")
    with pytest.raises(ValueError, match="survivor"):
        MergeResolver.resolve([a, b], survivor_id=uuid.uuid4())


def test_resolve_field_choices_override_defaults() -> None:
    first = _ref(citation_key="a", url="https://first.example", doi="10.1/aaa")
    second = _ref(
        citation_key="b", url="https://second.example", doi="10.2/bbb"
    )
    result = MergeResolver.resolve(
        [first, second],
        survivor_id=first.id,
        field_choices={"url": second.id},
    )
    assert result.merged_fields["url"] == "https://second.example"


def test_resolve_authors_unioned_by_default() -> None:
    first = _ref(citation_key="a", authors=["Ian Goodfellow"], doi="10.1/aaa")
    second = _ref(citation_key="b", authors=["Yoshua Bengio"])
    result = MergeResolver.resolve([first, second])
    assert result.merged_fields["authors"] == [
        "Ian Goodfellow",
        "Yoshua Bengio",
    ]


def test_resolve_field_choice_authors_replaces_not_unions() -> None:
    first = _ref(citation_key="a", authors=["Ian Goodfellow"])
    second = _ref(citation_key="b", authors=["Yann LeCun", "Yoshua Bengio"])
    result = MergeResolver.resolve(
        [first, second],
        survivor_id=first.id,
        field_choices={"authors": second.id},
    )
    assert result.merged_fields["authors"] == ["Yann LeCun", "Yoshua Bengio"]


def test_resolve_falls_back_to_survivor_for_unchosen_fields() -> None:
    first = _ref(citation_key="a", url="https://first.example", doi="10.1/aaa")
    second = _ref(citation_key="b", url="https://second.example", doi=None)
    result = MergeResolver.resolve(
        [first, second],
        survivor_id=first.id,
        field_choices={"url": second.id},
    )
    assert "doi" not in result.merged_fields


def test_resolve_fills_empty_survivor_field_from_others() -> None:
    first = _ref(citation_key="a", doi=None)
    second = _ref(citation_key="b", doi="10.1000/xyz")
    result = MergeResolver.resolve([first, second], survivor_id=first.id)
    assert result.merged_fields["doi"] == "10.1000/xyz"


def test_resolve_ids_to_delete_excludes_survivor() -> None:
    first = _ref(citation_key="a")
    second = _ref(citation_key="b")
    third = _ref(citation_key="c")
    result = MergeResolver.resolve([first, second, third], survivor_id=first.id)
    assert first.id not in result.ids_to_delete
    assert set(result.ids_to_delete) == {second.id, third.id}


def test_compute_plan_picks_most_complete() -> None:
    sparse = _read(_ref(citation_key="a", doi=None, url=None))
    full = _read(
        _ref(citation_key="b", doi="10.1000/xyz", url="https://x.example")
    )
    survivor_id, _defaults = MergeResolver.compute_plan([sparse, full])
    assert survivor_id == full.id


def test_compute_plan_defaults_field_to_first_non_empty() -> None:
    first = _read(_ref(citation_key="a", url="https://first.example"))
    second = _read(_ref(citation_key="b", url=None))
    _survivor_id, defaults = MergeResolver.compute_plan([second, first])
    assert defaults["url"] == first.id


def test_compute_plan_defaults_field_to_survivor_when_set() -> None:
    first = _read(_ref(citation_key="a", url="https://first.example"))
    second = _read(_ref(citation_key="b", url="https://second.example"))
    survivor_id, defaults = MergeResolver.compute_plan([first, second])
    assert defaults["url"] == survivor_id
