import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.extraction.worker import run_indexing


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Extract PDF text with mupdf and build semantic embeddings for "
            "the refree library. Idempotent: only (re-)processes papers "
            "whose PDF changed since the last pass. Safe to re-run."
        ),
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Number of references to process per pass (default: 100).",
    )
    args = parser.parse_args()
    stats = run_indexing(batch_size=args.batch_size)
    print(
        f"scanned={stats.scanned} extracted={stats.extracted} "
        f"re_extracted={stats.re_extracted} embedded={stats.embedded} "
        f"completed_scans={stats.completed_scans}"
    )


if __name__ == "__main__":
    main()
