import dataclasses
import io
import json

import pypdfium2 as pdfium
from PIL import Image

from rater.extraction.normalise import RawExtraction, RawField
from rater.extraction.ocr import PageText
from rater.extraction.providers.base import PageInput
from rater.extraction.schema import FIELD_NAMES
from rater.pipeline import Deps, run_pipeline
from rater.switches import Switches
from tests.resolve.conftest import gridset


class FakeOcr:
    name = "rapidocr"
    version = "test"

    def __init__(self, text: str) -> None:
        self.text = text

    def ocr(self, image: Image.Image) -> PageText:
        return PageText(self.name, self.version, self.text, tuple(self.text.splitlines()))


class FakeTess(FakeOcr):
    name = "tesseract"


class FakeExtractor:
    name = "rules"

    def __init__(self, values: dict[str, str]) -> None:
        self.values = values
        self.seen: list[PageInput] = []

    def extract(self, pages: list[PageInput]) -> RawExtraction:
        self.seen = pages
        out = {n: RawField(None, None, None) for n in FIELD_NAMES}
        for k, v in self.values.items():
            out[k] = RawField(v, 1, f"{k} {v}")
        return out


def blank_pdf() -> bytes:
    doc = pdfium.PdfDocument.new()
    doc.new_page(595, 842)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def deps(values: dict[str, str]) -> Deps:
    text = "\n".join(f"{k} {v}" for k, v in values.items())
    ex = FakeExtractor(values)
    return Deps(
        gridset=gridset(),
        engines=(FakeOcr(text), FakeTess(text)),
        primary=ex,
        fallback=ex,
        switches=Switches(),
        grid_manifest="manifest-sha",
    )


CAR = {
    "insurer": "Acme General Insurance Ltd",
    "vehicleClass": "Private Car",
    "policyType": "Private Car Package Policy",
    "rto": "ZZ01",
    "fuel": "Petrol",
    "cc": "1200",
    "manufactureYear": "2020",
    "policyStartDate": "01/03/2026",
    "businessType": "Renewal",
    "odPremium": "15,000",
    "ncb": "20",
}


def test_pipeline_blank_pdf_unsupported() -> None:
    r = run_pipeline(blank_pdf(), "blank.pdf", deps({}))
    assert r.status == "unsupported" and "no policy facts found" in r.trace[-1].decision.lower()


def test_pipeline_resolves_and_records_meta() -> None:
    r = run_pipeline(blank_pdf(), "upload.pdf", deps(CAR))
    assert r.status == "resolved"
    meta = r.meta
    assert meta["extractor"] == "rules" and meta["gridManifest"] == "manifest-sha"
    assert meta["ocr"] == {"rapidocr": "test", "tesseract": "test"} and len(meta["pdfSha256"]) == 64
    assert r.facts.cc.verification == "verified_both" and r.facts.cc.policy_citation == "upload.pdf · page 1"


def test_clarify_override_marked_and_linked() -> None:
    values = dict(CAR)
    del values["cc"]
    first = run_pipeline(blank_pdf(), "upload.pdf", deps(values))
    assert first.status == "ambiguous" and first.clarification == {"facts": ["cc"]}
    second = run_pipeline(blank_pdf(), "upload.pdf", deps(values), overrides={"cc": "1200"})
    assert second.status == "resolved"
    assert second.facts.cc.verification == "reviewer_supplied" and second.facts.cc.value == 1200
    assert "reviewer-supplied" in (second.facts.cc.note or "")


def test_pipeline_output_for_worker_is_valid_json() -> None:
    from rater.pipeline import AnalysisPipeline

    out = AnalysisPipeline(deps(CAR))(blank_pdf(), "upload.pdf")
    body = json.loads(out.result_json)
    assert out.status == body["status"] == "resolved"
    assert out.switches == Switches().as_dict() and out.versions["extractor"] == "rules"


def multi_page_pdf(n: int) -> bytes:
    doc = pdfium.PdfDocument.new()
    for _ in range(n):
        doc.new_page(595, 842)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def test_only_the_first_pages_are_read() -> None:
    assert Deps.__dataclass_fields__["read_pages"].default == 20
    d = dataclasses.replace(deps(CAR), read_pages=6)
    result = run_pipeline(multi_page_pdf(9), "long.pdf", d)
    assert len(d.primary.seen) == 6  # type: ignore[attr-defined]
    assert result.meta["pagesRead"] == 6 and result.meta["pageCount"] == 9
