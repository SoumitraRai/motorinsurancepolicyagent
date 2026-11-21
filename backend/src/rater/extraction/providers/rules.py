"""Local rule-based extractor: generic insurance-schedule labels matched against OCR rows.

It is the fallback when no LLM is configured or the LLM call fails, so the app always returns a result.
Each match returns the whole row as its quote (so verification can find it) and the row's page. The label
table holds generic schedule wording only; it is never tuned to a particular sample's values (NN5).
"""

import re

from rater.extraction.normalise import RawExtraction, RawField
from rater.extraction.providers.base import PageInput
from rater.extraction.schema import FIELD_NAMES

_AMOUNT = r"[\d,]+(?:\.\d+)?"
_DATE = r"\d{1,2}[\s/.-]+(?:\d{1,2}|[A-Za-z]{3,9})[\s,/.-]+\d{4}"

# field -> patterns tried in order; group 1 is the value. Case-insensitive, matched within one row.
_LABELS: dict[str, tuple[str, ...]] = {
    "insurer": (
        r"^([A-Z][A-Za-z&.\s]*?\bGENERAL\s+INSURANCE(?:\s+COMPANY)?(?:\s+(?:LTD|LIMITED|CO)\.?)?)",
        r"^([A-Z][A-Za-z&.\s]*?\bINSURANCE\s+(?:COMPANY\s+)?(?:LTD|LIMITED)\.?)",
    ),
    "previousInsurer": (
        r"previous\s+(?:policy|insurer)\b.*?\bof\s+([A-Z][A-Z&.\s]*?INSURANCE[A-Z.\s]*?(?:LTD|LIMITED|CO)\.?)",
        r"previous\s+insurer\s*[:\-]?\s*([A-Za-z][A-Za-z&.\s]+)",
    ),
    "businessType": (r"\b(new\s+business|brand\s+new|renewal|roll\s*over)\b",),
    "vehicleClass": (
        r"\b(private\s+car|two\s+wheeler|goods\s+carrying|passenger\s+carrying|school\s+bus|"
        r"motor\s*cycle|scooter|taxi)\b",
    ),
    "policyType": (
        r"\b((?:private\s+car|two\s+wheeler|motor)?\s*(?:package|comprehensive|liability\s+only|"
        r"stand[\s-]?alone\s+(?:tp|od|own\s+damage)|own\s+damage\s+only)\s+policy)\b",
    ),
    "make": (r"\bmake\b\s*(?:/\s*model\b\s*(?:&\s*variant)?)?\s*[:/\-]?\s*([A-Z][A-Z]+)",),
    "model": (
        r"\bmodel\b(?:\s*/\s*vehicle\s+variant)?(?:\s*\(sub-type\))?\s*[:/\-]?\s*([A-Z0-9][A-Z0-9 .\-/()]+)",
    ),
    "fuel": (r"fuel\s*type\s*[:\-]?\s*(petrol|diesel|cng|lpg|electric|hybrid|bi-?fuel[^,]*)",),
    "registrationNumber": (
        r"registration\s*(?:no|number)\.?\s*[:\-]?\s*([A-Z]{2}[\s-]*\d{1,2}[\s-]*[A-Z]{0,3}[\s-]*\d{1,4})",
    ),
    "rtoLocation": (r"rto\s*(?:location)?\s*[:\-]?\s*([A-Za-z][A-Za-z ,\-]{2,})",),
    "cc": (r"(?:cubic\s*capacity|cc\s*/\s*hp|engine\s*capacity|\bcc\b)\D{0,20}?(\d{2,5})",),
    "manufactureYear": (
        r"(?:year\s*of\s*(?:manufacture|mfg\.?)|mfg\.?\s*(?:month\s*&\s*)?year)\s*[:\-]?\s*"
        r"([A-Za-z0-9\-/]+)",
    ),
    "registrationYear": (r"(?:year\s*of\s*regn\.?|date\s*of\s*registration)\s*[:\-]?\s*([0-9\-/A-Za-z]+)",),
    "ncb": (
        r"no\s*claim\s*bonus\s*\(\s*(\d{1,2})\s*%\s*\)",
        r"deduct\s*(\d{1,2})\s*%\s*for\s*ncb",
        r"\bncb\s*[:\-]?\s*(\d{1,2})\s*%",
    ),
    "odPremium": (rf"(?:net|total)\s+own\s+damage\s+premium\D{{0,15}}?({_AMOUNT})",),
    "tpPremium": (rf"(?:net|total)\s+liability\s+premium\D{{0,15}}?({_AMOUNT})",),
    "netPremium": (rf"(?:total\s+premium(?:\s+payable)?|net\s+premium)\D{{0,15}}?({_AMOUNT})",),
    "policyStartDate": (rf"(?:period\s+of\s+insurance|policy\s+period)?.*?\bfrom\b\D{{0,25}}?({_DATE})",),
    "issueDate": (rf"(?:issuance|issue)\s*date\s*[:\-]?\s*({_DATE})",),
    "seatingCapacity": (r"seat(?:ing)?\s*(?:capacity)?(?:\s*including\s*driver)?\s*[:\-]?\s*(\d{1,3})\b",),
    "gvw": (r"\bgvw\b\s*[:\-]?\s*(\d{3,6})",),
}


class RulesExtractor:
    name = "rules"

    def extract(self, pages: list[PageInput]) -> RawExtraction:
        out: RawExtraction = {n: RawField(None, None, None) for n in FIELD_NAMES}
        for name, patterns in _LABELS.items():
            hit = self._first(pages, patterns)
            if hit:
                out[name] = hit
        return out

    @staticmethod
    def _first(pages: list[PageInput], patterns: tuple[str, ...]) -> RawField | None:
        for pattern in patterns:
            rx = re.compile(pattern, re.I)
            for p in pages:
                for row in p.text.splitlines():
                    m = rx.search(row.strip())
                    if m and m.group(1).strip():
                        return RawField(value=" ".join(m.group(1).split()), page=p.page, quote=row.strip())
        return None
