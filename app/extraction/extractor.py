from pathlib import Path

import pymupdf


class PdfTextExtractor:
    def extract(self, path: Path) -> str:
        document = pymupdf.open(path)
        try:
            pages = [str(page.get_text()) for page in document]
        finally:
            document.close()
        return "\n".join(pages).strip()
