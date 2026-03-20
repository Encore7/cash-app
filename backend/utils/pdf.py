from __future__ import annotations

from io import BytesIO

from pypdf import PdfReader


def extract_pdf_text(content: bytes) -> str:
    reader = PdfReader(BytesIO(content))
    pages: list[str] = []
    for page in reader.pages:
        pages.append(page.extract_text() or '')
    return '\n'.join(pages).strip()
