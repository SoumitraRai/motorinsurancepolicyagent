"""The extractor boundary (amended spec SR5/AC15): an LLM provider or local rules, never both deciding.

Whatever the extractor returns is only a claim: code checks every quote against the page (B3) and every
value is re-parsed by `normalise`. If the primary extractor fails in any way, the local rules extractor
runs instead and the result records which one ran.
"""

import os
from dataclasses import dataclass
from typing import Any, Protocol

from rater.extraction.normalise import RawExtraction, RawField
from rater.extraction.schema import FIELD_NAMES


class ExtractionError(Exception):
    """The extractor failed or returned something that isn't valid extraction output."""


@dataclass(frozen=True)
class PageInput:
    page: int
    text: str  # page-tagged OCR text (or the text layer)
    image_png: bytes | None


class Extractor(Protocol):
    name: str

    def extract(self, pages: list[PageInput]) -> RawExtraction: ...


def validate(data: Any) -> RawExtraction:
    """Strictly check extractor output against the schema; raise ExtractionError on any deviation."""
    if not isinstance(data, dict) or set(data) != set(FIELD_NAMES):
        raise ExtractionError("output does not have exactly the schema's fields")
    out: RawExtraction = {}
    for name in FIELD_NAMES:
        f = data[name]
        if not isinstance(f, dict) or set(f) != {"value", "page", "quote"}:
            raise ExtractionError(f"field {name} is malformed")
        value, page, quote = f["value"], f["page"], f["quote"]
        if value is not None and not isinstance(value, str):
            raise ExtractionError(f"field {name}.value is not a string")
        if page is not None and (not isinstance(page, int) or isinstance(page, bool) or page < 1):
            raise ExtractionError(f"field {name}.page is not a page number")
        if quote is not None and not isinstance(quote, str):
            raise ExtractionError(f"field {name}.quote is not a string")
        out[name] = RawField(value=value, page=page, quote=quote)
    return out


def choose_extractor() -> Extractor:
    from rater.extraction.providers.openrouter import OpenRouterExtractor
    from rater.extraction.providers.rules import RulesExtractor

    provider = os.environ.get("EXTRACTION_PROVIDER", "openrouter")
    key, model = os.environ.get("OPENROUTER_API_KEY", ""), os.environ.get("EXTRACTION_MODEL", "")
    if provider == "openrouter" and key and model:
        return OpenRouterExtractor(key, model)
    return RulesExtractor()


def extract_with_fallback(
    pages: list[PageInput], primary: Extractor, fallback: Extractor
) -> tuple[RawExtraction, str, str | None]:
    """(extraction, name of the extractor that ran, why the primary was not used — or None)."""
    if primary.name == fallback.name:
        return fallback.extract(pages), fallback.name, None
    try:
        return primary.extract(pages), primary.name, None
    except ExtractionError as exc:
        return fallback.extract(pages), fallback.name, f"{primary.name} failed: {exc}"
