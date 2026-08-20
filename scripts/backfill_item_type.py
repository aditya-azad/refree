import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import argparse
import time
from dataclasses import dataclass, field

import httpx
from sqlalchemy import text

from app.common.database import create_db_and_tables, engine
from app.common.logging import logger

_CROSSREF_BASE = "https://api.crossref.org/works"
_CROSSREF_DELAY_SECONDS = 1.0
_CROSSREF_TIMEOUT_SECONDS = 30.0
_DEFAULT_MAILTO = "refree-backfill@example.com"

_CROSSREF_TYPE_TO_ZOTERO: dict[str, str] = {
    "journal-article": "journalArticle",
    "proceedings-article": "conferencePaper",
    "book-chapter": "bookSection",
    "book-section": "bookSection",
    "book-part": "bookSection",
    "book": "book",
    "edited-book": "book",
    "monograph": "book",
    "reference-book": "book",
    "dissertation": "thesis",
    "posted-content": "preprint",
    "report": "report",
    "report-series": "report",
    "dataset": "dataset",
    "standard": "standard",
    "standard-series": "standard",
}


@dataclass
class BackfillStats:
    total: int = 0
    already_set: int = 0
    arxiv: int = 0
    found: int = 0
    found_by_type: dict[str, int] = field(default_factory=dict)
    not_found: int = 0
    no_doi_preprint: int = 0
    no_doi_indeterminate: int = 0
    errors: int = 0

    @property
    def set_count(self) -> int:
        return self.arxiv + self.found + self.no_doi_preprint

    @property
    def unset_count(self) -> int:
        return self.not_found + self.no_doi_indeterminate + self.errors

    def report(self) -> None:
        logger.info("item_type backfill complete")
        lines = [
            f"  total references      : {self.total}",
            f"  already had item_type : {self.already_set}",
            f"  set this run          : {self.set_count}",
            f"    - arXiv (preprint)  : {self.arxiv}",
            f"    - no-DOI (preprint)  : {self.no_doi_preprint}",
            f"    - Crossref found     : {self.found}",
        ]
        for item_type, count in sorted(
            self.found_by_type.items(), key=lambda kv: -kv[1]
        ):
            lines.append(f"        . {item_type:<18}: {count}")
        lines += [
            f"  not set this run     : {self.unset_count}",
            f"    - Crossref 404      : {self.not_found}",
            f"    - no-DOI + venue     : {self.no_doi_indeterminate}",
            f"    - errors             : {self.errors}",
        ]
        print("\n".join(lines))


def _is_arxiv_doi(doi: str) -> bool:
    return doi.lower().startswith("10.48550/arxiv.")


def _has_venue(publication_title: str | None, publisher: str | None) -> bool:
    return bool(
        (publication_title and publication_title.strip())
        or (publisher and publisher.strip())
    )


def _crossref_item_type(
    doi: str, client: httpx.Client
) -> tuple[str | None, str | None]:
    response = client.get(f"{_CROSSREF_BASE}/{doi}")
    if response.status_code == 404:
        return None, "crossref_not_found"
    if not response.is_success:
        return None, f"crossref_http_{response.status_code}"
    message = response.json().get("message", {})
    crossref_type = message.get("type", "")
    if not crossref_type:
        return None, "crossref_no_type"
    item_type = _CROSSREF_TYPE_TO_ZOTERO.get(crossref_type)
    if item_type is None:
        return crossref_type, "crossref_unmapped"
    return item_type, None


def _load_rows(force: bool) -> list[dict[str, str | None]]:
    query = text(
        "SELECT id, doi, publication_title, publisher, item_type "
        "FROM reference"
    )
    with engine.connect() as conn:
        rows = conn.execute(query).mappings().all()
    result: list[dict[str, str | None]] = []
    for row in rows:
        current = row["item_type"]
        if current and not force:
            continue
        result.append(
            {
                "id": str(row["id"]),
                "doi": row["doi"],
                "publication_title": row["publication_title"],
                "publisher": row["publisher"],
            }
        )
    return result


def _resolve_item_type(
    row: dict[str, str | None], client: httpx.Client, stats: BackfillStats
) -> tuple[str | None, bool]:
    doi = row["doi"]
    if doi and _is_arxiv_doi(doi):
        stats.arxiv += 1
        return "preprint", False
    if doi:
        item_type, reason = _crossref_item_type(doi, client)
        if item_type is not None:
            stats.found += 1
            stats.found_by_type[item_type] = (
                stats.found_by_type.get(item_type, 0) + 1
            )
            return item_type, True
        if reason == "crossref_not_found":
            stats.not_found += 1
        else:
            stats.errors += 1
            logger.warning(
                "crossref lookup failed for doi=%s: %s", doi, reason
            )
        return None, True
    if _has_venue(row["publication_title"], row["publisher"]):
        stats.no_doi_indeterminate += 1
        return None, False
    stats.no_doi_preprint += 1
    return "preprint", False


def backfill_item_type(force: bool, mailto: str) -> BackfillStats:
    create_db_and_tables()
    stats = BackfillStats()
    with engine.connect() as conn:
        stats.total = conn.execute(
            text("SELECT COUNT(*) FROM reference")
        ).scalar_one()
    rows = _load_rows(force)
    skipped = stats.total - len(rows)
    stats.already_set = skipped
    logger.info(
        "processing %d references (%d already set, skipped)",
        len(rows),
        skipped,
    )
    headers = {"User-Agent": f"refree/0.1 (mailto:{mailto})"}
    updates: list[tuple[str, str]] = []
    with httpx.Client(
        headers=headers,
        timeout=_CROSSREF_TIMEOUT_SECONDS,
        follow_redirects=True,
    ) as client:
        for i, row in enumerate(rows, start=1):
            item_type, queried = _resolve_item_type(row, client, stats)
            if item_type is not None:
                updates.append((item_type, row["id"]))
            if i % 50 == 0:
                logger.info("progress: %d/%d", i, len(rows))
            if queried:
                time.sleep(_CROSSREF_DELAY_SECONDS)
    update_stmt = text(
        "UPDATE reference SET item_type = :item_type, "
        "updated_at = CURRENT_TIMESTAMP WHERE id = :id"
    )
    with engine.begin() as conn:
        for item_type, row_id in updates:
            conn.execute(
                update_stmt,
                {"item_type": item_type, "id": row_id},
            )
    logger.info("wrote %d item_type values", len(updates))
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Backfill the item_type column on stored references. "
            "arXiv DOIs -> preprint; publisher DOIs -> Crossref; "
            "no-DOI/bare -> preprint; no-DOI+venue -> NULL."
        ),
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-derive item_type even for rows that already have a value.",
    )
    parser.add_argument(
        "--mailto",
        default=_DEFAULT_MAILTO,
        help="Contact email for the Crossref polite pool User-Agent.",
    )
    args = parser.parse_args()
    stats = backfill_item_type(force=args.force, mailto=args.mailto)
    stats.report()


if __name__ == "__main__":
    main()
