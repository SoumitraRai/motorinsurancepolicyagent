"""One analysis run: OCR → extraction (LLM or rules) → quote checks and normalisation → deterministic
resolution. Only `extraction/providers` talks to an LLM; resolution sees typed facts only.
"""

import hashlib
import io
import json
import time
from dataclasses import dataclass

from rater.extraction.normalise import apply_overrides, normalise
from rater.extraction.ocr import OcrEngine, ocr_document, versions
from rater.extraction.providers.base import Extractor, PageInput, extract_with_fallback
from rater.extraction.render import iter_pages
from rater.facts import Facts
from rater.grids.model import GridSet
from rater.resolve.engine import ENGINE_VERSION, resolve
from rater.result import ConfidenceOut, RateOut, Result, TraceStep
from rater.switches import Switches
from rater.worker import PipelineOutput

LLM_IMAGE_DPI = 150


@dataclass(frozen=True)
class Deps:
    gridset: GridSet
    engines: tuple[OcrEngine, ...]
    primary: Extractor
    fallback: Extractor
    switches: Switches
    grid_manifest: str


def _png(image: object) -> bytes:
    buf = io.BytesIO()
    image.save(buf, format="PNG", optimize=True)  # type: ignore[attr-defined]
    return buf.getvalue()


def _no_facts(facts: Facts, file_name: str) -> Result:
    reason = "No policy facts found in this document; it may not be a motor policy schedule."
    return Result(
        status="unsupported",
        facts=facts,
        rates={c: RateOut(applicable=None, rate_percent=None, reason=reason) for c in ("od", "tp")},
        trace=[TraceStep(step=1, kind="result", decision=reason)],
        confidence=ConfidenceOut(level="low", reason="nothing could be read from the document"),
    )


def run_pipeline(pdf: bytes, file_name: str, deps: Deps, overrides: dict[str, str] | None = None) -> Result:
    started = time.monotonic()
    pages = ocr_document(pdf, deps.engines)
    llm = deps.primary.name != deps.fallback.name
    images = [_png(img) for img in iter_pages(pdf, LLM_IMAGE_DPI)] if llm else [None] * len(pages)
    inputs = [
        PageInput(page=p.page, text=p.best_text, image_png=img) for p, img in zip(pages, images, strict=True)
    ]
    raw, used, note = extract_with_fallback(inputs, deps.primary, deps.fallback)
    facts = normalise(raw, pages, file_name)
    if overrides:
        facts = apply_overrides(facts, overrides)

    if not any(getattr(facts, name).known for name in type(facts).model_fields):
        result = _no_facts(facts, file_name)
    else:
        result = resolve(facts, deps.gridset, deps.switches, file_name)
    result.meta.update(
        {
            "engine": ENGINE_VERSION,
            "extractor": used,
            "extractorNote": note,
            "model": getattr(deps.primary, "model", None) if used != "rules" else None,
            "ocr": versions(deps.engines),
            "gridManifest": deps.grid_manifest,
            "pdfSha256": hashlib.sha256(pdf).hexdigest(),
            "pages": len(pages),
            "switches": deps.switches.as_dict(),
            "reviewerSupplied": sorted(overrides) if overrides else [],
            "seconds": round(time.monotonic() - started, 1),
        }
    )
    return result


class AnalysisPipeline:
    """The worker's pipeline: grids are loaded once; each call is one run."""

    def __init__(self, deps: Deps) -> None:
        self.deps = deps

    def __call__(self, pdf: bytes, file_name: str, overrides: dict[str, str] | None = None) -> PipelineOutput:
        result = run_pipeline(pdf, file_name, self.deps, overrides)
        body = result.to_json()
        meta = json.loads(body)["meta"]
        return PipelineOutput(
            status=result.status,
            result_json=body,
            versions={k: meta.get(k) for k in ("engine", "extractor", "model", "ocr", "gridManifest")},
            switches=self.deps.switches.as_dict(),
        )
