"""Local OCR (intent B4): RapidOCR is the main text source, Tesseract the cross-check.

Pages with a real text layer are not OCR'd (their text is used directly, B2). Image pages are OCR'd one
at a time by default (`OCR_WORKERS`, default 1): one page with both engines peaks around 1 GB of memory.
"""

import itertools
import os
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Protocol

import pytesseract
from PIL import Image

from rater.extraction.render import iter_pages, text_layer

MIN_TEXT_LAYER_CHARS = 40  # below this a page is treated as image-only


@dataclass(frozen=True)
class PageText:
    engine: str
    version: str
    text: str
    rows: tuple[str, ...]


@dataclass(frozen=True)
class PageEvidence:
    page: int
    text_layer: str
    by_engine: dict[str, str] = field(default_factory=dict)  # engine name -> text (rows joined by newlines)

    @property
    def best_text(self) -> str:
        return self.text_layer or self.by_engine.get("rapidocr") or self.by_engine.get("tesseract", "")


class OcrEngine(Protocol):
    name: str

    def ocr(self, image: Image.Image) -> PageText: ...


class RapidOcrEngine:
    name = "rapidocr"

    def __init__(self) -> None:
        self._engine: Any = None

    def _load(self) -> Any:
        if self._engine is None:
            from rapidocr_onnxruntime import RapidOCR

            self._engine = RapidOCR()
        return self._engine

    @property
    def version(self) -> str:
        import importlib.metadata

        return importlib.metadata.version("rapidocr-onnxruntime")

    def ocr(self, image: Image.Image) -> PageText:
        boxes, _ = self._load()(image)
        rows = _rebuild_rows(boxes or [])
        return PageText(self.name, self.version, "\n".join(rows), tuple(rows))


def _rebuild_rows(boxes: list[Any]) -> list[str]:
    """RapidOCR returns separate text boxes; join boxes that share a baseline into one row, left to right."""
    items = []
    for quad, text, _score in boxes:
        ys = [p[1] for p in quad]
        xs = [p[0] for p in quad]
        items.append((min(ys), max(ys), min(xs), str(text)))
    items.sort(key=lambda it: ((it[0] + it[1]) / 2, it[2]))
    rows: list[list[tuple[float, float, float, str]]] = []
    for it in items:
        mid = (it[0] + it[1]) / 2
        if rows:
            top = min(x[0] for x in rows[-1])
            bottom = max(x[1] for x in rows[-1])
            if top <= mid <= bottom:
                rows[-1].append(it)
                continue
        rows.append([it])
    return [" ".join(x[3] for x in sorted(r, key=lambda x: x[2])) for r in rows]


class TesseractEngine:
    name = "tesseract"

    @property
    def version(self) -> str:
        return str(pytesseract.get_tesseract_version())

    def ocr(self, image: Image.Image) -> PageText:
        text = pytesseract.image_to_string(image, config="--psm 6")
        rows = tuple(line for line in text.splitlines() if line.strip())
        return PageText(self.name, self.version, "\n".join(rows), rows)


def _ocr_page(args: tuple[int, Image.Image, tuple[OcrEngine, ...]]) -> PageEvidence:
    number, image, engines = args
    return PageEvidence(page=number, text_layer="", by_engine={e.name: e.ocr(image).text for e in engines})


def ocr_document(
    pdf: bytes,
    engines: tuple[OcrEngine, ...],
    dpi: int = 300,
    max_pages: int | None = None,
    only_pages: set[int] | None = None,
) -> list[PageEvidence]:
    """OCR evidence for the first `max_pages` pages (all when None), or only the page numbers given."""
    layers = text_layer(pdf)
    if max_pages is not None:
        layers = layers[:max_pages]
    workers = max(1, int(os.environ.get("OCR_WORKERS", "1")))
    jobs = []
    out: dict[int, PageEvidence] = {}
    pages = itertools.islice(iter_pages(pdf, dpi), len(layers))
    for number, (layer, image) in enumerate(zip(layers, pages, strict=True), start=1):
        if only_pages is not None and number not in only_pages:
            continue
        if len(layer) >= MIN_TEXT_LAYER_CHARS:
            out[number] = PageEvidence(page=number, text_layer=layer)
            continue
        if workers == 1:
            out[number] = _ocr_page((number, image, engines))
        else:
            jobs.append((number, image, engines))
    if jobs:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            for ev in pool.map(_ocr_page, jobs):
                out[ev.page] = ev
    return [out[n] for n in sorted(out)]


def versions(engines: tuple[OcrEngine, ...]) -> dict[str, str]:
    result = {}
    for e in engines:
        try:
            result[e.name] = e.version  # type: ignore[attr-defined]
        except Exception:  # version lookup must never fail a run
            result[e.name] = "unknown"
    return result
