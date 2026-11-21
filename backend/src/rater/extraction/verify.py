"""Quote verification (intent B3, spec SR6): is the extractor's quote really on the page it cites?

Comparison ignores case and all whitespace, because RapidOCR drops spaces ("CubicCapacityWatts").
"""

from rater.extraction.ocr import PageEvidence
from rater.facts import Verification


def _squash(text: str) -> str:
    return "".join(text.split()).lower()


def verify_quote(quote: str | None, page: PageEvidence | None) -> Verification:
    if not quote or page is None:
        return "unverified"
    q = _squash(quote)
    if not q:
        return "unverified"
    if page.text_layer and q in _squash(page.text_layer):
        return "text_layer"
    hits = sum(1 for text in page.by_engine.values() if q in _squash(text))
    if hits >= 2:
        return "verified_both"
    return "verified_one" if hits == 1 else "unverified"
