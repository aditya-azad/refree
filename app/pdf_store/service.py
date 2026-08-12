import re
from pathlib import Path

_UNSAFE_CHARS = re.compile(r'[\\/:*?"<>|\s]+')


def _sanitize_filename_part(value: str) -> str:
    return _UNSAFE_CHARS.sub("", value).strip()


class PdfStore:
    def __init__(self, pdf_dir: Path) -> None:
        self._pdf_dir = pdf_dir

    def store(self, filename: str, pdf_bytes: bytes) -> Path:
        self._pdf_dir.mkdir(parents=True, exist_ok=True)
        path = self._pdf_dir / filename
        if path.exists():
            stem, _, ext = filename.rpartition(".")
            counter = 1
            while path.exists():
                path = self._pdf_dir / f"{stem}_{counter}.{ext}"
                counter += 1
        path.write_bytes(pdf_bytes)
        return path.relative_to(self._pdf_dir)

    @staticmethod
    def build_filename(last_name: str, year: str, title: str) -> str:
        stem = _sanitize_filename_part(f"{last_name}{year}{title}")
        if not stem:
            stem = "untitled"
        return f"{stem}.pdf"
