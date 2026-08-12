import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import argparse

from that_depends.providers.context_resources import (
    ContextScopes,
    container_context,
)

from app.common.database import create_db_and_tables
from app.zotero_import.container import ZoteroImportContainer


def _detect_zotero_storage_dir() -> Path:
    default = Path.home() / "Zotero" / "storage"
    if default.is_dir() and any(default.iterdir()):
        return default
    profile_dir = Path.home() / ".zotero" / "zotero"
    if profile_dir.is_dir():
        for prefs in profile_dir.rglob("prefs.js"):
            for line in prefs.read_text(errors="ignore").splitlines():
                if "extensions.zotero.dataDir" in line:
                    parts = line.split('"')
                    if len(parts) >= 4:
                        return Path(parts[-2]) / "storage"
    return default


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import references from a running Zotero + Better BibTeX instance.",
    )
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:23119",
        help="Zotero local server base URL.",
    )
    parser.add_argument(
        "--zotero-storage-dir",
        default=None,
        help="Zotero storage directory (containing per-key attachment folders). "
        "Defaults to auto-detection from the Zotero profile directory.",
    )
    args = parser.parse_args()
    storage_dir = (
        Path(args.zotero_storage_dir)
        if args.zotero_storage_dir
        else _detect_zotero_storage_dir()
    )
    create_db_and_tables()
    with (
        container_context(scope=ContextScopes.REQUEST),
        ZoteroImportContainer.zotero_base_url.init(args.base_url),
        ZoteroImportContainer.zotero_storage_dir.init(storage_dir),
    ):
        service = ZoteroImportContainer.zotero_import_service.resolve_sync()
        result = service.import_all()
        print(result.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
