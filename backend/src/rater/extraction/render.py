"""PDF pages as images (for OCR and the extraction model) and as text (the PDF's own text layer)."""

from collections.abc import Iterator

import pypdfium2 as pdfium
from PIL import Image


def page_count(pdf: bytes) -> int:
    doc = pdfium.PdfDocument(pdf)
    try:
        return len(doc)
    finally:
        doc.close()


def iter_pages(pdf: bytes, dpi: int = 300) -> Iterator[Image.Image]:
    """One page image at a time, so a long policy never holds every page in memory (plan.md memory note)."""
    doc = pdfium.PdfDocument(pdf)
    try:
        for i in range(len(doc)):
            yield doc[i].render(scale=dpi / 72).to_pil().convert("RGB")
    finally:
        doc.close()


def render_pages(pdf: bytes, dpi: int = 300) -> list[Image.Image]:
    return list(iter_pages(pdf, dpi))


def text_layer(pdf: bytes) -> list[str]:
    doc = pdfium.PdfDocument(pdf)
    try:
        out = []
        for i in range(len(doc)):
            tp = doc[i].get_textpage()
            out.append(tp.get_text_range().strip())
            tp.close()
        return out
    finally:
        doc.close()
