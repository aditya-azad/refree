import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import argparse

from that_depends.providers.context_resources import (
    ContextScopes,
    container_context,
)

from app.zotero_import.container import ZoteroImportContainer


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import references from a running Zotero + Better BibTeX instance.",
    )
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:23119",
        help="Zotero local server base URL.",
    )
    args = parser.parse_args()
    with (
        container_context(scope=ContextScopes.REQUEST),
        ZoteroImportContainer.zotero_base_url.init(args.base_url),
    ):
        service = ZoteroImportContainer.zotero_import_service.resolve_sync()
        result = service.import_all()
        print(result.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
