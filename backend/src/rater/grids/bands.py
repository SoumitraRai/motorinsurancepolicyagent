"""Parse the range labels used across the grids into explicit intervals (spec C6: gaps stay gaps).

Supported forms (as written in the supplied files): `<1000`, `>1000`, `1000-1500`, `<1000CC`,
`1000 CC-1500 CC`, `<10k`, `>10-50k`, `>50k-1L`, `>2L`, `<10`, `Upto 5years`, `Above 5 Years`,
`0-5 years`, `All`. A leading `>` on a range (`>10-50k`) makes its lower end exclusive.
"""

import math
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Band:
    lo: float
    hi: float
    lo_incl: bool
    hi_incl: bool
    unit: str
    label: str

    def contains(self, x: float) -> bool:
        above = x > self.lo or (self.lo_incl and x == self.lo)
        below = x < self.hi or (self.hi_incl and x == self.hi)
        return above and below


_MULT = {"": 1, "k": 1_000, "l": 100_000, "lac": 100_000, "lakh": 100_000, "cr": 10_000_000}
_NUM = r"(\d+(?:\.\d+)?)\s*(k|l|lac|lakh|cr)?"


def _num(value: str, suffix: str | None) -> float:
    return float(value) * _MULT[(suffix or "").lower()]


def parse_band(label: str, unit: str) -> Band | None:
    text = label.strip()
    if not text:
        return None
    norm = re.sub(r"\s*(cc|years?|yrs?)\b", "", text, flags=re.I).strip()
    if norm.lower() == "all":
        return Band(-math.inf, math.inf, True, True, unit, label)

    m = re.fullmatch(rf"(>)?\s*{_NUM}\s*-\s*{_NUM}", norm, flags=re.I)
    if m:
        gt, a, sa, b, sb = m.groups()
        hi_suffix = sb
        lo_suffix = sa or (sb if gt else None)  # ">10-50k": both ends are in thousands
        return Band(_num(a, lo_suffix), _num(b, hi_suffix), not gt, True, unit, label)

    m = re.fullmatch(rf"([<>])\s*{_NUM}", norm, flags=re.I)
    if m:
        op, a, sa = m.groups()
        v = _num(a, sa)
        return (
            Band(-math.inf, v, True, False, unit, label)
            if op == "<"
            else Band(v, math.inf, False, True, unit, label)
        )

    m = re.fullmatch(rf"(upto|up to|above)\s*{_NUM}", norm, flags=re.I)
    if m:
        word, a, sa = m.groups()
        v = _num(a, sa)
        if word.lower() == "above":
            return Band(v, math.inf, False, True, unit, label)
        return Band(-math.inf, v, True, True, unit, label)

    m = re.fullmatch(rf"{_NUM}\+", norm, flags=re.I)
    if m:
        return Band(_num(m.group(1), m.group(2)), math.inf, True, True, unit, label)
    return None
