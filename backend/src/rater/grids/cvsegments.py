"""Commercial-vehicle segment labels (Go Digit `CV Grid (excl. HCV)`) → rule dimensions.

Returns a `CvSegment`, or a reason string when the text is not recognised. When part of a label's scope is
not defined in the file (e.g. "Low CD2 RTOs @ 10% CD2" without naming the RTOs, "High HP" without a
threshold), the rest is still parsed and `undefined` holds the reason: a policy that matches the defined
part gets a cited `ambiguous`, never a guessed rate. Catch-all rows ("GCV4 excl above") are marked
`catch_all`; they cover only what no other row covers, which the adapter cannot decide row by row.

Readings (README assumptions): tonnage bands are gross vehicle weight in tonnes, `a to b T` = (a, b],
`upto x T` = [0, x], `x T and above` = [x, ∞), `x T+` = (x, ∞) (it follows an `a-x T` row);
"non-diesel" = petrol/CNG/LPG (EVs have their own segments);
"n+1 seater" = n+1 seats including the driver.
"""

import math
import re
from dataclasses import dataclass

from rater.grids.bands import Band
from rater.grids.model import ContainsAny, DimValue, NotContainsAny

_UNDEFINED = (
    (r"\([^)]*low[\s_]*cd2\s*rtos[^)]*\)", "applies only to 'Low CD2 RTOs', which the sheet does not list"),
    (r"\([^)]*declined\s*rtos[^)]*\)", "applies only to 'Declined RTOs', which the sheet does not list"),
    (r"\([^)]*sel(?:e)?ctive\s*body[^)]*\)", "applies only to unnamed 'selective body types'"),
    (r"-?\s*\b(?:high|low)\s*hp\b", "splits tractors by High/Low HP without stating the threshold"),
)
_CATCH_ALL: tuple[tuple[str, list[tuple[str, DimValue]]], ...] = (
    (r"^gcv\s*4\s*excl(?:uding)?\s*above$", [("vehicle_class", "gcv")]),
    (
        r"^all\s*other\s*segments\s*of\s*pcv,\s*misc\s*d,\s*tractor$",
        [("vehicle_class", frozenset({"pcv_2w", "pcv_3w", "pcv_taxi", "misc_d", "tractor"}))],
    ),
)
_PREFIXES: tuple[tuple[str, list[tuple[str, DimValue]]], ...] = (
    (r"gcv\s*3", [("vehicle_class", "gcv_3w")]),
    (r"gcv\s*4", [("vehicle_class", "gcv")]),
    (r"pcv\s*3\s*w?", [("vehicle_class", "pcv_3w")]),
    (r"pcv\s*2\s*w?", [("vehicle_class", "pcv_2w")]),
    (r"pcv\s*4(?:\s*wheeler)?", [("vehicle_class", "pcv_taxi")]),
    (r"e-?\s*rickshaw|e-?\s*auto", [("vehicle_class", "pcv_3w"), ("fuel", "electric")]),
    (r"e-?\s*loaders?", [("vehicle_class", "gcv_3w"), ("fuel", "electric")]),
    (r"misc\.?\s*d", [("vehicle_class", "misc_d")]),
    (r"jcb", [("vehicle_class", "misc_d"), ("body_type", ContainsAny(frozenset({"JCB"})))]),
    (
        r"backhoe loader,\s*forklift,\s*excavator,\s*and\s*loader",
        [
            ("vehicle_class", "misc_d"),
            ("body_type", ContainsAny(frozenset({"BACKHOE", "FORKLIFT", "EXCAVATOR", "LOADER"}))),
        ],
    ),
    (r"tractors?", [("vehicle_class", "tractor")]),
)
_NUM = r"(\d+(?:\.\d+)?)"


@dataclass(frozen=True)
class CvSegment:
    label: str
    dims: tuple[tuple[str, DimValue], ...]
    undefined: str | None = None  # why part of the scope can't be decided from the file
    catch_all: bool = False


def _band(lo: float, hi: float, lo_incl: bool, hi_incl: bool, unit: str, label: str) -> Band:
    return Band(lo, hi, lo_incl, hi_incl, unit, label)


def _take(pattern: str, text: str) -> tuple[re.Match[str] | None, str]:
    m = re.search(pattern, text, re.I)
    return (m, (text[: m.start()] + " " + text[m.end() :]).strip()) if m else (None, text)


def parse_cv_segment(label: str) -> CvSegment | str:
    text = " ".join(str(label).split())
    for pattern, catch_dims in _CATCH_ALL:
        if re.match(pattern, text, re.I):
            reason = f"segment '{text}' covers only what no other row covers"
            return CvSegment(text, tuple(catch_dims), reason, catch_all=True)
    undefined = None
    body = text
    for pattern, reason in _UNDEFINED:
        m, body = _take(pattern, body)
        if m:
            undefined = f"segment '{text}' {reason}"
            break

    dims: list[tuple[str, DimValue]] = []
    rest = ""
    for pattern, prefix_dims in _PREFIXES:
        m = re.match(pattern, body, re.I)
        if m:
            dims += prefix_dims
            rest = body[m.end() :]
            break
    else:
        return f"segment '{text}' is not a recognised commercial-vehicle segment"
    vc = dict(dims)["vehicle_class"]

    m, rest = _take(r"\(\s*excluding\s+kolkata\s+rtos\s*\)", rest)
    if m:
        dims.append(("rto_location", NotContainsAny(frozenset({"KOLKATA"}))))
    m, rest = _take(r"\(\s*kolkata\s+rtos\s*\)", rest)
    if m:
        dims.append(("rto_location", ContainsAny(frozenset({"KOLKATA"}))))
    m, rest = _take(r"-\s*without\s*zd\b", rest)
    if m:
        dims.append(("zero_dep", "no"))

    # Fuel
    for pattern, value in (
        (r"\bnon-?\s*diesel\b", frozenset({"petrol", "cng", "lpg"})),
        (r"\bdiesel\b", "diesel"),
        (r"-\s*petrol\s*/\s*cng\b", frozenset({"petrol", "cng"})),
        (r"-\s*others\b", frozenset({"diesel", "lpg", "electric", "hybrid"})),
        (r"\bpetrol\s*/\s*cng\b", frozenset({"petrol", "cng"})),
        (r"\bcng\b", "cng"),
    ):
        m, rest = _take(pattern, rest)
        if m:
            dims.append(("fuel", value))
            break

    # Seating
    m, rest = _take(r"(\d+)\s*\+\s*1\s*seater", rest)
    if m:
        n = int(m.group(1)) + 1
        dims.append(("seating_capacity", _band(n, n, True, True, "seats", m.group(0))))
    m, rest = _take(r"greater\s+than\s+(\d+)\s*seater", rest)
    if m:
        dims.append(("seating_capacity", _band(int(m.group(1)), math.inf, False, True, "seats", m.group(0))))

    # Gross vehicle weight (goods vehicles)
    if vc == "gcv":
        for pattern, kind in (
            (rf"up\s*to\s*{_NUM}\s*-\s*{_NUM}\s*t\b", "range"),
            (rf"{_NUM}\s*t?\s*(?:to|-)\s*{_NUM}\s*t\b", "range"),
            (rf"^\s*{_NUM}\s*(?:to|-)\s*{_NUM}(?=\s|$)", "range"),
            (rf"up\s*to\s*{_NUM}\s*t\b", "upto"),
            (rf"{_NUM}\s*t\s*and\s*above", "above"),
            (rf"{_NUM}\s*t\s*\+", "plus"),
        ):
            m, rest2 = _take(pattern, rest)
            if m:
                rest = rest2
                if kind == "range":
                    dims.append(
                        ("gvw_t", _band(float(m.group(1)), float(m.group(2)), False, True, "t", m.group(0)))
                    )
                elif kind == "upto":
                    dims.append(("gvw_t", _band(0, float(m.group(1)), True, True, "t", m.group(0))))
                else:
                    lo_incl = kind == "above"
                    dims.append(("gvw_t", _band(float(m.group(1)), math.inf, lo_incl, True, "t", m.group(0))))
                break

    # Vehicle age (years)
    age_patterns = (
        (r"greater\s+than\s+(\d+)\s*(?:years?|yrs?)?", lambda g: (int(g[0]), math.inf, False)),
        (r">\s*(\d+)\s*(?:years?|yrs?)?", lambda g: (int(g[0]), math.inf, False)),
        (r"(?:age\s*)?(\d+)\s*&\s*(\d+)", lambda g: (int(g[0]), int(g[1]), True)),
        (
            r"(?:up\s*to\s*)?(?:age\s*)?(\d+)\s*(?:to|-)\s*(\d+)\s*(?:years?|yrs?|yr)?",
            lambda g: (int(g[0]), int(g[1]), True),
        ),
        (r"(?:age\s*)?(\d+)\s*\+\s*(?:years?|yrs?|yr|age)?", lambda g: (int(g[0]), math.inf, True)),
        (r"(?:age\s*)?(\d+)\s*(?:years?|yrs?|yr|age)\b", lambda g: (int(g[0]), int(g[0]), True)),
        (r"(?:age\s*)(\d+)\b", lambda g: (int(g[0]), int(g[0]), True)),
        (r"^\s*-?\s*(\d+)\s*$", lambda g: (int(g[0]), int(g[0]), True)),
    )
    for pattern, build in age_patterns:
        m, rest2 = _take(pattern, rest)
        if m:
            lo, hi, lo_incl = build(m.groups())
            dims.append(("age", _band(lo, hi, lo_incl, True, "years", m.group(0).strip())))
            rest = rest2
            break

    leftover = re.sub(r"[\s\-–,()]|\bage\b|\byears?\b|\bwheeler\b", "", rest, flags=re.I)
    if leftover:
        return f"segment '{text}' has unrecognised text '{rest.strip()}'"
    return CvSegment(text, tuple(sorted(dims, key=lambda d: d[0])), undefined)
