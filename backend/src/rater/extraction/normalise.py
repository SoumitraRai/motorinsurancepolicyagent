"""Deterministic normalisation of extracted values into typed facts (spec SR7–SR10).

The extractor (LLM or local rules) supplies, per field, a value, the 1-based page and a verbatim quote.
Here code checks the quote (B3) and turns text into canonical values. Anything it cannot parse becomes
`unknown` with a note; nothing is guessed (NN3).
"""

import re
from dataclasses import dataclass
from datetime import date
from typing import Any

from rater import insurers
from rater.extraction.ocr import PageEvidence
from rater.extraction.verify import verify_quote
from rater.facts import Fact, Facts
from rater.grids import model_fuels
from rater.grids.makes import canonical_make


@dataclass(frozen=True)
class RawField:
    value: str | None
    page: int | None
    quote: str | None


RawExtraction = dict[str, RawField]

# camelCase extractor field names -> Facts attribute
FIELDS: dict[str, str] = {
    "insurer": "insurer",
    "previousInsurer": "previous_insurer",
    "businessType": "business_type",
    "vehicleClass": "vehicle_class",
    "make": "make",
    "model": "model",
    "fuel": "fuel",
    "registrationNumber": "rto",
    "rto": "rto",
    "rtoLocation": "rto_location",
    "cc": "cc",
    "manufactureYear": "manufacture_year",
    "registrationYear": "registration_year",
    "policyType": "policy_type",
    "ncb": "ncb",
    "previousNcb": "previous_ncb",
    "odPremium": "od_premium",
    "tpPremium": "tp_premium",
    "netPremium": "net_premium",
    "policyStartDate": "policy_start_date",
    "issueDate": "issue_date",
    "gvw": "gvw",
    "seatingCapacity": "seating_capacity",
    "segment": "segment",
    "odTermYears": "od_term_years",
    "addOns": "add_ons",
    "cngLpgKitValue": "cng_lpg_kit_value",
    "cpaCover": "cpa_cover",
    "bodyType": "body_type",
    "tppdRestricted": "tppd_restricted",
}

_MONTHS = {
    m: i
    for i, m in enumerate(
        ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], start=1
    )
}
_GENERIC = {"insurance", "general", "company", "co", "ltd", "limited", "the", "india", "of", "and"}


class _Unknown(Exception):
    """The text was present but could not be read as a value; carries the note shown to the reviewer."""


def _money(text: str) -> float:
    # OCR reads "₹" as "%", "®" or "2" next to amounts; strip bracketed symbols before reading digits.
    cleaned = re.sub(r"\(\s*[%®₹2]?\s*\)", " ", text)
    nums = re.findall(r"-?\d[\d,]*(?:\.\d+)?", cleaned)
    if not nums:
        raise _Unknown("no amount found")
    return float(nums[-1].replace(",", ""))


def _percent(text: str) -> float:
    if re.search(r"\(\s*%\s*\)", text):
        raise _Unknown("a '%' beside an amount is a misread rupee sign, not a percentage")
    m = re.search(r"(\d+(?:\.\d+)?)\s*%?", text)
    if not m:
        raise _Unknown("no percentage found")
    v = float(m.group(1))
    if not 0 <= v <= 100:
        raise _Unknown(f"{v:g} is not a valid percentage")
    return v


def _int(text: str) -> int:
    m = re.search(r"\d[\d,]*", text)
    if not m:
        raise _Unknown("no number found")
    return int(m.group(0).replace(",", ""))


def _year(text: str) -> int:
    if re.search(r"\b0{3,4}1?\b|0001-01-01", text):
        raise _Unknown("placeholder date on the policy (e.g. 0001-01-01): manufacture year unknown")
    m = re.search(r"\b(19[5-9]\d|20\d\d)\b", text)
    if not m:
        raise _Unknown("no plausible year found")
    return int(m.group(1))


def _date(text: str) -> str:
    t = text.strip()
    m = re.search(r"\b(\d{4})-(\d{2})-(\d{2})\b", t)
    if m:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3))).isoformat()
    m = re.search(r"\b(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})\b", t)
    if m:
        return date(int(m.group(3)), int(m.group(2)), int(m.group(1))).isoformat()
    m = re.search(r"\b(\d{1,2})[\s-]*([A-Za-z]{3})[a-z]*[\s,-]*(\d{4})\b", t)
    if m and m.group(2).lower() in _MONTHS:
        return date(int(m.group(3)), _MONTHS[m.group(2).lower()], int(m.group(1))).isoformat()
    raise _Unknown("no date found")


def _rto(text: str) -> str:
    # Registration numbers are often one token ("ZZ07AB1234"): no word boundary after the digits.
    m = re.search(r"\b([A-Z]{2})[\s-]*(\d{1,2})(?!\d)", text.upper())
    if not m:
        raise _Unknown("no RTO code found")
    return f"{m.group(1)}{int(m.group(2)):02d}"


def _fuel(text: str) -> str:
    t = text.lower()
    for word, fuel in (
        ("cng", "cng"),
        ("lpg", "lpg"),
        ("hybrid", "hybrid"),
        ("electric", "electric"),
        ("battery", "electric"),
        (" ev", "electric"),
        ("diesel", "diesel"),
        ("petrol", "petrol"),
    ):
        if word in f" {t}":
            return fuel
    raise _Unknown("fuel not recognised")


def _vehicle_class(text: str) -> str:
    t = text.lower()
    table = (
        (r"goods.*(three|3)\s*-?\s*wheeler|goods.*\b3w\b", "gcv_3w"),
        (r"passenger.*(two|2)\s*-?\s*wheeler|\bbike taxi\b", "pcv_2w"),
        (r"passenger.*(three|3)\s*-?\s*wheeler|e-?\s*rickshaw|e-?\s*auto\b", "pcv_3w"),
        (r"misc(ellaneous)?\b|special type", "misc_d"),
        (r"school bus", "school_bus"),
        (r"staff bus", "staff_bus"),
        (r"taxi|passenger carrying|pcv", "pcv_taxi"),
        (r"three wheeler|3w|auto rickshaw", "pcv_3w"),
        (r"goods carrying|gcv|truck|lorry", "gcv"),
        (r"tractor", "tractor"),
        (r"scooter", "scooter"),
        (r"motorcycle|motor cycle|motorbike|\bbike\b", "motorcycle"),
        (r"\bmoped\b", "moped"),
        (r"two wheeler|2w", "two_wheeler"),
        (r"private car|car|4w|four wheeler", "private_car"),
        (r"hatch ?back|sedan|saloon|\bsuv\b|\bmuv\b", "private_car"),  # car body styles
        (r"misc", "misc_d"),
    )
    for pattern, value in table:
        if re.search(pattern, t):
            return value
    raise _Unknown("vehicle class not recognised")


def _policy_type(text: str) -> str:
    t = text.lower()
    if re.search(r"liability only|third party only|stand.?alone tp|\bsatp\b|act only", t):
        return "satp"
    if re.search(r"own damage only|stand.?alone od|\bsaod\b|standalone own damage", t):
        return "saod"
    if re.search(r"comprehensive|package|bundled", t):
        return "comprehensive"
    raise _Unknown("policy type not recognised")


def _business(text: str) -> str:
    t = text.lower()
    if re.search(r"\bnew\b|brand new|first registration", t):
        return "new"
    if "renewal" in t:
        return "renewal"
    if re.search(r"roll ?over|ported", t):
        return "rollover"
    raise _Unknown("business type not recognised")


def _yes_no(text: str) -> str:
    t = text.strip().lower()
    if t in {"yes", "y", "true", "opted", "included"}:
        return "yes"
    if t in {"no", "n", "false", "not opted", "nil", "none"}:
        return "no"
    raise _Unknown("not a yes/no value")


def _body_type(text: str) -> str:
    t = " ".join(text.split()).upper()
    if not t:
        raise _Unknown("no body type")
    return t


def _tppd(text: str) -> str:
    t = text.lower()
    if re.search(r"restrict|limited\s*to", t):
        return "yes"
    if re.search(r"tppd\s*[:\-]?\s*(no|nil|not)\b|unrestricted", t):
        return "no"
    raise _Unknown("TPPD restriction not stated")


def _add_ons(text: str) -> list[str]:
    if text.strip().lower() in {"none", "nil", "na", "n/a", "-", ""}:
        return []
    return [p.strip() for p in re.split(r"[,;\n]", text) if p.strip()]


_PARSERS: dict[str, Any] = {
    "insurer": str.strip,
    "previous_insurer": str.strip,
    "business_type": _business,
    "vehicle_class": _vehicle_class,
    "make": canonical_make,
    "model": lambda t: " ".join(t.upper().split()),
    "fuel": _fuel,
    "rto": _rto,
    "rto_location": lambda t: " ".join(t.upper().split()),
    "cc": _int,
    "manufacture_year": _year,
    "registration_year": _year,
    "policy_type": _policy_type,
    "ncb": _percent,
    "previous_ncb": _percent,
    "od_premium": _money,
    "tp_premium": _money,
    "net_premium": _money,
    "policy_start_date": _date,
    "issue_date": _date,
    "gvw": _int,
    "seating_capacity": _int,
    "segment": str.strip,
    "od_term_years": _int,
    "add_ons": _add_ons,
    "cng_lpg_kit_value": _money,
    "cpa_cover": _yes_no,
    "body_type": _body_type,
    "tppd_restricted": _tppd,
}


def _same_insurer(a: str, b: str) -> bool:
    ca, cb = insurers.canonical(a), insurers.canonical(b)
    if ca or cb:
        return ca == cb
    words = lambda s: {w for w in re.findall(r"[a-z]+", s.lower()) if w not in _GENERIC}  # noqa: E731
    return bool(words(a)) and words(a) == words(b)


def _fuel_from_model(facts: Facts) -> None:
    """PO decision 2026-11-22: a model sold in one fuel only supplies the fuel the policy doesn't print."""
    if facts.fuel.known or not (facts.make.known and facts.model.known):
        return
    fuels = model_fuels.fuels_for(str(facts.make.value), str(facts.model.value))
    if fuels is None or len(fuels) != 1:
        return
    (fuel,) = fuels
    kit = facts.cng_lpg_kit_value.value
    if fuel == "petrol" and kit is not None and float(kit) > 0:
        facts.fuel = Fact(
            value=None,
            verification="not_found",
            note="the model is petrol-only but a CNG/LPG kit is fitted; fuel not decided",
        )
        return
    facts.fuel = Fact(
        value=fuel,
        raw=f"{facts.make.value} {facts.model.value}",
        page=facts.model.page,
        quote=facts.model.quote,
        verification="derived",
        policy_citation=facts.model.policy_citation,
        note=f"fuel not printed; {facts.make.value} {facts.model.value} is sold in {fuel} only per the "
        f"{model_fuels.SOURCE}",
    )


def normalise(raw: RawExtraction, pages: list[PageEvidence], file_name: str) -> Facts:
    by_page = {p.page: p for p in pages}
    facts = Facts()
    for name, field in raw.items():
        attr = FIELDS.get(name)
        if attr is None or field.value is None or str(field.value).strip() == "":
            continue
        if attr == "rto" and facts.rto.known and name == "registrationNumber":
            continue  # an explicit RTO code wins over one read from the registration number
        cite = f"{file_name} · page {field.page}" if field.page else None
        verification = verify_quote(field.quote, by_page.get(field.page or -1))
        try:
            value = _PARSERS[attr](str(field.value))
            setattr(
                facts,
                attr,
                Fact(
                    value=value,
                    raw=str(field.value),
                    page=field.page,
                    quote=field.quote,
                    verification=verification,
                    policy_citation=cite,
                ),
            )
        except _Unknown as exc:
            setattr(
                facts,
                attr,
                Fact(
                    value=None,
                    raw=str(field.value),
                    page=field.page,
                    quote=field.quote,
                    verification="not_found",
                    policy_citation=cite,
                    note=str(exc),
                ),
            )

    # SR9: a "liability only" title with an OD premium line contradicts itself; don't pick one.
    if facts.policy_type.value == "satp" and facts.od_premium.known and float(facts.od_premium.value) > 0:
        facts.policy_type = facts.policy_type.model_copy(
            update={
                "value": None,
                "verification": "not_found",
                "confidence": "unknown",
                "note": "the policy title says liability only but the schedule has an OD premium; "
                "these contradict",
            }
        )

    _fuel_from_model(facts)

    # SR8: business type from the insurers when the policy doesn't state it.
    if not facts.business_type.known and facts.insurer.known and facts.previous_insurer.known:
        same = _same_insurer(str(facts.insurer.value), str(facts.previous_insurer.value))
        facts.business_type = Fact(
            value="renewal" if same else "rollover",
            raw=f"{facts.insurer.value} / {facts.previous_insurer.value}",
            page=facts.previous_insurer.page,
            quote=facts.previous_insurer.quote,
            verification="derived",
            policy_citation=facts.previous_insurer.policy_citation,
            note="same current and previous insurer → renewal"
            if same
            else "different previous insurer → rollover",
        )
    return facts


def apply_overrides(facts: Facts, overrides: dict[str, str]) -> Facts:
    """Reviewer-supplied facts from /clarify (SR25), marked so they are never mistaken for document facts."""
    snake = {**{k: v for k, v in FIELDS.items()}, **{v: v for v in FIELDS.values()}}
    for name, text in overrides.items():
        attr = snake.get(name) or snake.get(
            "".join(w.capitalize() if i else w for i, w in enumerate(name.split("_")))
        )
        if attr is None:
            continue
        try:
            value = _PARSERS[attr](str(text))
        except _Unknown as exc:
            setattr(
                facts,
                attr,
                Fact(
                    value=None,
                    raw=str(text),
                    verification="not_found",
                    note=f"reviewer-supplied value could not be read: {exc}",
                ),
            )
            continue
        setattr(
            facts,
            attr,
            Fact(
                value=value,
                raw=str(text),
                verification="reviewer_supplied",
                note="reviewer-supplied fact (SR25), not read from the document",
            ),
        )
    return facts
