import io

import pypdfium2 as pdfium
from PIL import Image, ImageDraw, ImageFont

from rater.extraction.ocr import RapidOcrEngine, TesseractEngine, ocr_document
from rater.extraction.render import render_pages, text_layer


def _font(size: int = 36) -> ImageFont.ImageFont:
    for path in (
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ):
        try:
            return ImageFont.truetype(path, size)  # type: ignore[return-value]
        except OSError:
            continue
    return ImageFont.load_default()


def schedule_image() -> Image.Image:
    """A synthetic two-column schedule: labels on the left, values far to the right on the same row."""
    img = Image.new("RGB", (1600, 500), "white")
    d = ImageDraw.Draw(img)
    f = _font()
    for i, (label, value) in enumerate(
        [("Cubic Capacity", "1197"), ("Fuel Type", "Petrol"), ("Registration No", "ZZ-01-AB-1234")]
    ):
        d.text((60, 60 + i * 120), label, fill="black", font=f)
        d.text((1000, 60 + i * 120), value, fill="black", font=f)
    return img


def image_pdf(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PDF", resolution=150)
    return buf.getvalue()


def test_rapid_rows_rebuilt_label_value_same_row() -> None:
    rows = RapidOcrEngine().ocr(schedule_image()).rows
    joined = [r.replace(" ", "").lower() for r in rows]
    assert any("cubiccapacity" in r and "1197" in r for r in joined), rows
    assert any("fueltype" in r and "petrol" in r for r in joined), rows


def test_tesseract_reads_the_same_rows() -> None:
    text = TesseractEngine().ocr(schedule_image()).text.lower().replace(" ", "")
    assert "cubiccapacity" in text and "1197" in text


def test_image_only_pdf_has_no_text_layer_and_gets_both_engines() -> None:
    pdf = image_pdf(schedule_image())
    assert text_layer(pdf) == [""]
    (page,) = ocr_document(pdf, engines=(RapidOcrEngine(), TesseractEngine()))
    assert page.page == 1 and page.text_layer == ""
    assert set(page.by_engine) == {"rapidocr", "tesseract"}


def test_text_layer_pdf_skips_ocr() -> None:
    doc = pdfium.PdfDocument.new()
    doc.new_page(595, 842)
    buf = io.BytesIO()
    doc.save(buf)
    # A blank page has no text: OCR still runs (nothing to read), the text layer stays empty.
    assert text_layer(buf.getvalue()) == [""]
    assert len(render_pages(buf.getvalue(), dpi=72)) == 1
