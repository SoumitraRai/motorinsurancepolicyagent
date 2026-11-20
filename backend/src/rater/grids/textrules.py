"""Classify footnote, note and T&C lines read from the grids (spec SR18).

Kinds:
- `broker_side`: depends on the broker's business (volume, GWP, synergy mix). Never applied (D2).
- `policy_condition`: a condition on policy facts with an effect (`reduce`/`add`/`flat`/`decline`).
- `undefined_decline`: declines "few RTOs" without naming them; any policy in scope is ambiguous (C5).
- `slab_basis`: how a premium slab is computed (HDFC ERGO's GWP footnote, C1).
- `basis`: which premium a rate applies to.
- `definition`: vocabulary (what "Non Petrol" or "NCB" covers).
- `out_of_scope`: about a different product than the one being rated.
- `unclassified`: anything else. If it falls in the matched sheet's scope, the run is ambiguous.

Order matters: broker-side wording is checked before generic percentage wording.
"""

import re
from dataclasses import dataclass

_PRODUCT_WORDS = {
    "extended_warranty": r"\bEW\b|extended warranty",
    "school_bus": r"school\s*bus|\bSB\b",
    "gcv": r"\bGCV\b|\bM&HCV\b|\bHCV\b|\bLCV\b|goods carr",
    "pcv_taxi": r"\btaxi\b|kaali|kali peeli",
    "pcv_3w": r"\b3W\b|three wheeler",
    "two_wheeler": r"\bTW\b|\b2W\b|scooter|two wheeler",
}
_BROKER = re.compile(
    r"\bvolume\b|\b(lakh|lakhs|lac|crs?)\b.*\b(monthly|annual|business)\b|\bmonthly\b.*\b(lakh|lakhs|lac)\b"
    r"|\bGWP\b.*\brule\b|\bsynergy\b|\bpartners?\b|\bIMDs?\b|\bdeal basis\b|\benabler",
    re.I,
)
_PCT = r"(\d+(?:\.\d+)?)\s*%"


@dataclass(frozen=True)
class Classified:
    kind: str
    text: str
    effect: str | None = None
    percent: float | None = None


def _product_of(text: str) -> str | None:
    for product, pattern in _PRODUCT_WORDS.items():
        if re.search(pattern, text, re.I):
            return product
    return None


def classify(text: str, product: str) -> Classified:
    t = " ".join(text.split())
    low = t.lower()

    if re.search(r"slab", low) and re.search(r"\bgwp\b|achievement", low):
        return Classified("slab_basis", t)
    if _BROKER.search(t):
        return Classified("broker_side", t)

    other = _product_of(t)
    if other is not None and other != product:
        return Classified("out_of_scope", t)

    if re.search(r"\bfew\s+rtos?\b.*\bdeclined?\b", low):
        return Classified("undefined_decline", t)
    if re.search(r"\bdeclined?\b", low):
        return Classified("policy_condition", t, effect="decline")

    m = re.search(_PCT + r".*\b(lesser|less|reduced|redused|deducted|dedected)\b", t, re.I) or re.search(
        r"\b(reduced|redused|deducted|dedected)\b.*?" + _PCT, t, re.I
    )
    if m:
        pct = next(g for g in m.groups() if g and re.fullmatch(r"\d+(?:\.\d+)?", g))
        return Classified("policy_condition", t, effect="reduce", percent=float(pct))
    m = re.search(_PCT + r"\s*(additional|extra)", t, re.I)
    if m:
        return Classified("policy_condition", t, effect="add", percent=float(m.group(1)))
    m = re.search(r"\bflat\s+" + _PCT, t, re.I)
    if m:
        return Classified("policy_condition", t, effect="flat", percent=float(m.group(1)))

    if re.search(r"\bpayout\b.*\bon\b.*\bpremium\b", low):
        return Classified("basis", t)
    if re.search(r"\bincludes?\b|\bconsidered (as|in)\b", low):
        return Classified("definition", t)
    return Classified("unclassified", t)
