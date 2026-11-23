"""Local rule-based extractor: generic insurance-schedule labels matched against OCR rows.

It is the fallback when no LLM is configured or the LLM call fails, so the app always returns a result.
Each match returns the matched label and value as its quote, and the row's page. Only that span is quoted:
a row often holds several fields, and one misread character in another field must not fail the quote
check (PO 2026-11-23). The label
table holds generic schedule wording only; it is never tuned to a particular sample's values (NN5).
"""

import re

from rater.extraction.normalise import RawExtraction, RawField
from rater.extraction.providers.base import PageInput
from rater.extraction.schema import FIELD_NAMES
from rater.grids.makes import split_make

_AMOUNT = r"[\d,]+(?:\.\d+)?"
_DATE = r"\d{1,2}[\s/.-]+(?:\d{1,2}|[A-Za-z]{3,9})[\s,/.-]+\d{4}"

# field -> patterns tried in order; group 1 is the value. Case-insensitive, matched within one row.
_LABELS: dict[str, tuple[str, ...]] = {
    "insurer": (
        r"^([A-Z][A-Za-z&.\s]*?\bGENERAL\s+INSURANCE(?:\s+COMPANY)?(?:\s+(?:LTD|LIMITED|CO)\.?)?)",
        r"^([A-Z][A-Za-z&.\s]*?\bINSURANCE\s+(?:COMPANY\s+)?(?:LTD|LIMITED)\.?)",
    ),
    "previousInsurer": (
        r"previous\s*(?:policy|insurer).*?\bof\s+([A-Z][A-Z&.\s]*?INSURANCE[A-Z.\s]*?(?:LTD|LIMITED|CO)\.?)",
        r"previous\s*insurer\s*[:\-]?\s*([A-Za-z][A-Za-z&.\s]+)",
    ),
    # Only a labelled field: free text that mentions "renewal" is not the policy's business type.
    "businessType": (
        r"(?:business\s*type|type\s*of\s*business|policy\s*status|nature\s*of\s*business)\s*[:\-]?\s*"
        r"(new(?:\s*business)?|brand\s*new|renewal|roll\s*over)",
    ),
    "vehicleClass": (
        r"((?:goods|passenger)\s*carrying(?:\s*vehicle)?(?:\s*[-–]?\s*(?:three|two|3|2)\s*-?\s*wheeler)?|"
        r"private\s*car|two\s*wheeler|school\s*bus|staff\s*bus|e-?\s*rickshaw|miscellaneous|"
        r"(?:agricultural\s*)?tractor|motor\s*cycle|scooter|taxi)",
        r"(?:vehicle\s*type|body\s*type)\s*[:\-]?\s*(hatch\s*back|sedan|suv|muv|saloon)",
    ),
    "policyType": (
        r"((?:private\s*car|two\s*wheeler|motor)?\s*(?:package|comprehensive|liability\s*only|"
        r"stand[\s-]?alone\s*(?:tp|od|own\s*damage)|own\s*damage\s*only)\s*policy)",
    ),
    "make": (r"\bmake\b\s*(?:/\s*model\b\s*(?:&\s*variant)?)?\s*[:/\-]?\s*([A-Z][A-Z]+)",),
    "model": (
        r"\bmodel\b(?:\s*&\s*variant)?(?:\s*/\s*vehicle\s*variant)?(?:\s*\(\s*sub-?\s*type\s*\))?\s*[:/\-]?\s*"
        r"([A-Z0-9][A-Z0-9 .\-/()]+)",
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
    "policyStartDate": (
        rf"\bfrom\s*[:\-]?\s*(?:\d{{1,2}}:\d{{2}}(?::\d{{2}})?\s*(?:hrs)?\s*(?:on)?\s*)?({_DATE})",
        rf"(?:period\s+of\s+insurance|policy\s+period).*?\bfrom\b\D{{0,25}}?({_DATE})",
    ),
    "issueDate": (rf"(?:issuance|issue)\s*date\s*[:\-]?\s*({_DATE})",),
    "seatingCapacity": (r"seat(?:ing)?\s*(?:capacity)?(?:\s*including\s*driver)?\s*[:\-]?\s*(\d{1,3})\b",),
    "gvw": (r"\b(?:gvw|gross\s*vehicle\s*weight)\b\s*(?:\(\s*kgs?\s*\))?\s*[:\-]?\s*(\d{3,6})",),
    "bodyType": (r"body\s*type\s*[:\-]?\s*([A-Za-z][A-Za-z /&\-]{2,30}?)\s*(?:$|\n|\s{2,})",),
    "tppdRestricted": (r"(tppd\s*(?:cover\s*)?(?:restricted|limited)\s*to[^\n]{0,30}|restricted\s*tppd)",),
    "cngLpgKitValue": (rf"cng\s*/?\s*lpg\s*kit\D{{0,15}}?({_AMOUNT})",),
}


# A value never runs into the next label printed on the same row.
_NEXT_LABEL = re.compile(
    r"\s+(?:seating|fuel\s*type|cubic|chassis|engine\s*no|year\s*of|invoice|policy\s*no|date\s*of|"
    r"registration|gstin|hypothecation|body\s*type|cc\s*/\s*hp|mfg|issuance|total\s*premium|no\.?\s*of|"
    r"period\s*of|pincode|tel\b|no\b)\b.*$",
    re.I,
)
_TEXT_FIELDS = {"rtoLocation", "model", "make", "insurer", "previousInsurer"}
_SPLIT_LABEL = re.compile(r"(issuance|totalpremium|seating|fuel|cubic)", re.I)  # labels glued to a value


class RulesExtractor:
    name = "rules"

    def extract(self, pages: list[PageInput]) -> RawExtraction:
        out: RawExtraction = {n: RawField(None, None, None) for n in FIELD_NAMES}
        for name, patterns in _LABELS.items():
            hit = self._first(pages, patterns)
            if hit and name in _TEXT_FIELDS and hit.value:
                trimmed = _NEXT_LABEL.sub("", hit.value).strip(" ,-")
                trimmed = _SPLIT_LABEL.split(trimmed)[0].strip(" ,-") if name == "rtoLocation" else trimmed
                if name == "make":
                    trimmed = split_make(trimmed)
                hit = RawField(trimmed or None, hit.page, hit.quote)
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
                        return RawField(
                            value=" ".join(m.group(1).split()), page=p.page, quote=m.group(0).strip()
                        )
        return None
