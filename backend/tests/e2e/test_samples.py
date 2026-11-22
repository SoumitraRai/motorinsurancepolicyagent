"""End-to-end on the four supplied samples (AC21). Structure and citations only, never a rate (NN5).

Slow (OCR of 40 pages with two engines), so it runs with `make e2e`, not `make test`.
"""

import json
import os
from functools import lru_cache
from pathlib import Path

import pytest

from rater.bundle import BUNDLE_ROOT
from rater.citations import PdfGridCite, XlsxCite
from rater.config import build_deps
from rater.extraction.providers.rules import RulesExtractor
from rater.grids.readback import _lines, _workbook, check
from rater.pipeline import Deps, run_pipeline
from rater.result import Result

pytestmark = pytest.mark.e2e
SAMPLES = sorted((BUNDLE_ROOT / "sample-policies").glob("*.pdf"))


@lru_cache(maxsize=2)
def deps(extractor: str) -> Deps:
    d = build_deps()
    if extractor == "rules":
        return Deps(d.gridset, d.engines, RulesExtractor(), RulesExtractor(), d.switches, d.grid_manifest)
    return d


def _cell_exists(c: dict) -> bool:  # type: ignore[type-arg]
    if c["type"] == "xlsx":
        cite = XlsxCite(c["file"], c["sheet"], c["range"])
        return (
            _workbook(BUNDLE_ROOT / cite.file).sheet(cite.sheet).value(cite.range.split(":")[0]) is not None
        )
    if c["type"] == "pdf_grid":
        cite = PdfGridCite(c["file"], c["page"], c["table"], c["row"])
        return any(ln.page == cite.page and cite.row in ln.text for ln in _lines(BUNDLE_ROOT / cite.file))
    return True


EXTRACTORS = ["rules"] + (
    ["openrouter"] if os.environ.get("OPENROUTER_API_KEY") and os.environ.get("EXTRACTION_MODEL") else []
)


@pytest.mark.parametrize("extractor", EXTRACTORS)
@pytest.mark.parametrize("pdf", SAMPLES, ids=[p.stem for p in SAMPLES])
def test_sample_structure(pdf: Path, extractor: str) -> None:
    result = run_pipeline(pdf.read_bytes(), pdf.name, deps(extractor))
    body = json.loads(result.to_json())
    Result.model_validate(body)  # schema-valid round trip
    assert body["status"] in {"resolved", "unsupported", "ambiguous"}
    assert {"status", "facts", "rates", "trace", "confidence"} <= set(body)

    for step in body["trace"]:
        for c in step["citations"]:
            assert _cell_exists(c), (step["decision"], c)
    for comp in ("od", "tp"):
        rate = body["rates"][comp]
        if rate["ratePercent"] is not None:
            (c,) = rate["citations"]
            cite = (
                XlsxCite(c["file"], c["sheet"], c["range"])
                if c["type"] == "xlsx"
                else PdfGridCite(c["file"], c["page"], c["table"], c["row"])
            )
            assert check(BUNDLE_ROOT, cite, rate["rawCellValue"]), cite.render()
        assert rate["ratePercent"] != 0 or rate["applicable"] is not False  # never "0%" for not applicable

    if "-satp-" in pdf.name and body["facts"]["policyType"]["value"] == "satp":
        assert body["rates"]["od"]["applicable"] is False and body["rates"]["od"]["ratePercent"] is None
