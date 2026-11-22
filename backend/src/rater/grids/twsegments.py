"""Two-wheeler segment labels (Go Digit `TW …`/`2W …` sheets) → rule dimensions.

A label expands to one or more alternatives (OR); each alternative is a tuple of (dimension, value) that
must all hold (AND). Examples from the files:
  `SCOOTER`, `MC`, `SCOOTER/MC`, `SC/EV` (a scooter, or any EV), `SC_EV` (an electric scooter),
  `MC <=155`, `MC_180-350_RE`, `MC <= 180 Hero/Honda`, `MC_180-350_Others` ("Others" = makes not named
  by a sibling label with the same type and CC band), `MC_180-350_Other than RE`, `3-7 KW` (EV power),
  `< =350`, `All`.
Unknown labels raise, so a new layout fails loudly at load time instead of matching wrongly.
"""

import re

from rater.grids.bands import parse_band
from rater.grids.makes import KNOWN_MAKES, canonical_make
from rater.grids.model import Contains, DimValue, NotIn

Alternative = tuple[tuple[str, DimValue], ...]

# Model families named inside make groups ("HONDA/JAWA/Avenger"): (make, model family).
_MODEL_FAMILIES = {"AVENGER": ("BAJAJ", "AVENGER")}
_KNOWN = {canonical_make(m) for m in KNOWN_MAKES}
_TYPE_PREFIX = re.compile(r"^(SCOOTER/MC|SCOOTER/EV|SC/EV|SC_EV|SCOOTER|SC|MC)(?![A-Z])", re.I)


def _split(label: str) -> tuple[str, str, str]:
    """(type token, CC band text, make text)."""
    raw = label.strip()
    m = _TYPE_PREFIX.match(raw)
    kind = m.group(1).upper() if m else ""
    rest = raw[m.end() :] if m else raw
    rest = rest.replace("_", " ").strip()
    bm = re.match(r"^((?:[<>]\s*=?\s*\d+)|(?:\d+\s*-\s*\d+))\s*(.*)$", rest)
    band, makes = (bm.group(1), bm.group(2).strip()) if bm else ("", rest)
    return kind, band.replace(" ", ""), makes


def _types(kind: str) -> list[list[tuple[str, DimValue]]]:
    if kind == "SCOOTER/MC":
        return [[("tw_type", frozenset({"scooter", "motorcycle"}))]]
    if kind in ("SCOOTER/EV", "SC/EV"):
        return [[("tw_type", "scooter")], [("fuel", "electric")]]
    if kind == "SC_EV":
        return [[("tw_type", "scooter"), ("fuel", "electric")]]
    if kind in ("SCOOTER", "SC"):
        return [[("tw_type", "scooter")]]
    if kind == "MC":
        return [[("tw_type", "motorcycle")]]
    return [[]]


def _make_names(text: str) -> list[str]:
    return [canonical_make(p.strip()) for p in text.split("/") if p.strip()]


def parse_tw_segment(label: str, siblings: list[str]) -> list[Alternative]:
    text = label.strip()
    if text.lower() == "all":
        return [()]
    if text.upper() == "EV":
        return [(("fuel", "electric"),)]
    if re.search(r"\bkw\b", text, re.I):
        band = parse_band(text, "kw")
        if band is None:
            raise ValueError(f"two-wheeler segment: unreadable power band {label!r}")
        return [(("fuel", "electric"), ("power_kw", band))]

    kind, band_text, makes = _split(text)
    base: list[tuple[str, DimValue]] = []
    if band_text:
        band = parse_band(band_text, "cc")
        if band is None:
            raise ValueError(f"two-wheeler segment: unreadable CC band {label!r}")
        base.append(("cc", band))
    if not kind and not band_text and makes.upper() == "RE":
        kind, makes = "MC", "RE"
    if not kind and not band_text and not makes:
        raise ValueError(f"two-wheeler segment: unknown label {label!r}")

    make_alts: list[list[tuple[str, DimValue]]]
    low = makes.lower()
    if not makes:
        make_alts = [[]]
    elif low == "others":
        named = {
            m
            for s in siblings
            if s.strip() != text and _split(s)[:2] == (kind, band_text)
            for m in _make_names(_split(s)[2])
            if m not in ("OTHERS",) and m not in _MODEL_FAMILIES
        }
        make_alts = [[("make", NotIn(frozenset(named)))]]
    elif low.startswith("other than"):
        make_alts = [[("make", NotIn(frozenset(_make_names(makes[len("other than") :]))))]]
    else:
        names = _make_names(makes)
        unknown = [n for n in names if n not in _KNOWN and n not in _MODEL_FAMILIES]
        if unknown:
            raise ValueError(f"two-wheeler segment: unknown make text in {label!r}")
        plain = [n for n in names if n not in _MODEL_FAMILIES]
        make_alts = [[("make", frozenset(plain))]] if plain else []
        for n in names:
            if n in _MODEL_FAMILIES:
                fam_make, family = _MODEL_FAMILIES[n]
                make_alts.append([("make", fam_make), ("model", Contains(family))])

    out: list[Alternative] = []
    for t in _types(kind):
        for mk in make_alts:
            out.append(tuple(sorted(t + base + mk, key=lambda d: d[0])))
    return out
