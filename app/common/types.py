import re
from datetime import UTC, datetime
from typing import Annotated
from urllib.parse import urlparse

from pydantic import AfterValidator, BeforeValidator


def _ensure_utc(value: datetime | str) -> datetime:
    if isinstance(value, str):
        value = datetime.fromisoformat(value)
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _validate_url(value: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        msg = "invalid URL: must be a valid http(s) URL"
        raise ValueError(msg)
    return value


def _validate_doi(value: str) -> str:
    if not re.match(r"^10\.\d{4,}/\S+$", value):
        msg = "invalid DOI: expected format '10.<registrant>/<suffix>'"
        raise ValueError(msg)
    return value


def _clean_authors(value: list[str] | str) -> list[str]:
    if isinstance(value, str):
        value = value.split(",")
    cleaned = [a.strip() for a in value]
    return [a for a in cleaned if a]


def _clean_doi(value: str) -> str:
    cleaned = value.strip()
    cleaned = re.sub(
        r"^https?://(?:dx\.)?doi\.org/", "", cleaned, flags=re.IGNORECASE
    )
    cleaned = re.sub(r"^doi:\s*", "", cleaned, flags=re.IGNORECASE)
    return cleaned.strip()


def _clean_url(value: str) -> str:
    cleaned = value.strip()
    if cleaned and "://" not in cleaned:
        cleaned = f"http://{cleaned}"
    return cleaned


def _fix_spacing(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


ProperWhitespacedStr = Annotated[str, BeforeValidator(_fix_spacing)]
Authors = Annotated[list[str], BeforeValidator(_clean_authors)]
UTCDatetime = Annotated[datetime, BeforeValidator(_ensure_utc)]
DOI = Annotated[str, BeforeValidator(_clean_doi), AfterValidator(_validate_doi)]
URL = Annotated[str, BeforeValidator(_clean_url), AfterValidator(_validate_url)]
