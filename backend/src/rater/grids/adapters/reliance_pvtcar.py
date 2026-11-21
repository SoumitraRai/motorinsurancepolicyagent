"""Reliance private car "Old Business" grid: region × fuel/policy type, OD payout (and STP), with the
`RTO List` RTO → region map and the private-car-relevant T&C (column H, hygiene and synergy sections).

The `RTO List` names regions ("Up1", "Rom", "Chennai"…) that the rate rows describe differently
("UP, Haryana , Rajasthan", "Rest Of Maharashtra", "TamilNadu"…). The file never links the two, so the
link is made, in order, by:
1. a city the rate row names itself (e.g. "Kolkata");
2. a documented spelling/abbreviation alias (e.g. "Rom" → rest of Maharashtra, "Up1" → UP);
3. the documented city → state list (`geo.CITY_STATE`; PO decision 2026-11-21), confidence capped.
The RTO List's zone must agree with the rate row's zone; if not, both are offered and the run is ambiguous.
Codes missing from the RTO List fall back to their state code (`geo.STATE_CODES`), also capped.
"""

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from rater.citations import XlsxCite
from rater.grids import geo
from rater.grids.bands import parse_band
from rater.grids.model import (
    DimValue,
    ExceptionRule,
    Grid,
    MappingRow,
    RateCell,
    RateRule,
    RtoRegionTable,
    Unpublished,
)
from rater.grids.textrules import classify
from rater.grids.xlsx import MISSING, Workbook
from rater.resolve.confidence import Cap

INSURER = "Reliance"
SHEET = "PRIVATE CAR COMP, SAOD & STP"
CITY_CAP = Cap("medium", "region found through the documented city → state reference list")
STATE_CAP = Cap("medium", "region found through the RTO's state code (not in the grid's RTO List)")

# Abbreviations and misspellings in the rate rows' region labels.
_ROW_TOKENS = {
    "KA": "KARNATAKA",
    "TS": "TELANGANA",
    "AP": "ANDHRA PRADESH",
    "HP": "HIMACHAL PRADESH",
    "JK": "JAMMU AND KASHMIR",
    "UP": "UTTAR PRADESH",
    "GUJRAT": "GUJARAT",
    "TAMILNADU": "TAMIL NADU",
    "BANGLORE": "BANGALORE",
}
# Abbreviations in the RTO List's region names (beyond plain state and city names).
_REGION_ALIASES: dict[str, tuple[str, ...]] = {
    "UP1": ("UTTAR PRADESH",),
    "UP2": ("UTTAR PRADESH",),
    "ROM": ("MAHARASHTRA",),
    "GUJ1": ("GUJARAT",),
    "HPANDJAMMU": ("HIMACHAL PRADESH", "JAMMU AND KASHMIR"),
    "NORTHEAST": tuple(sorted(geo.NORTH_EAST)),
    "TAMILNADU": ("TAMIL NADU",),
}
_STATES = set(geo.STATE_CODES.values())
_FUELS: dict[str, frozenset[str]] = {
    "C": frozenset({"petrol", "cng", "lpg"}),  # "Petrol/Bifuel/Comp"
    "D": frozenset({"diesel", "electric"}),  # "Diesel/EV/Comp"
}


def _norm(text: str) -> str:
    return "".join(ch for ch in str(text).upper() if ch.isalnum())


@dataclass(frozen=True)
class _Row:
    label: str
    zone: str
    states: frozenset[str]
    cities: frozenset[str]
    rest: bool  # "Rest of …": the states minus cities that other rows name


def _parse_row(label: str, zone: str) -> _Row:
    text = label.strip()
    rest = text.lower().startswith("rest of")
    body = re.sub(r"(?i)^rest of\s*", "", text)
    states: set[str] = set()
    cities: set[str] = set()
    for raw in re.split(r"\s*,\s*", body):
        tok = " ".join(raw.upper().split())
        if not tok:
            continue
        tok = _ROW_TOKENS.get(tok.replace(" ", ""), tok)
        if tok == "NE":
            states |= geo.NORTH_EAST
        elif tok in _STATES:
            states.add(tok)
        elif geo.state_of_city(tok):
            cities.add(tok)
        else:
            raise ValueError(f"Reliance '{SHEET}': unknown region token {raw!r} in {label!r}")
    return _Row(text, zone, frozenset(states), frozenset(cities), rest)


def _month_year(text: str) -> date | None:
    m = re.search(r"\b([A-Za-z]{3})[a-z]*[-' ]*(\d{2})\b", text)
    months = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
    if not m or m.group(1).upper() not in months:
        return None
    return date(2000 + int(m.group(2)), months.index(m.group(1).upper()) + 1, 1)


def _resolve_region(name: str, rows: list[_Row]) -> tuple[_Row | None, str, Cap | None]:
    key = _norm(name)
    for row in rows:  # 1. a city the rate row names itself
        if any(_norm(c) == key for c in row.cities):
            return row, "", None
    if key in _REGION_ALIASES:  # 2. documented abbreviation
        states, note, cap = _REGION_ALIASES[key], f"'{name}' read as {' + '.join(_REGION_ALIASES[key])}", None
    elif " ".join(name.upper().split()) in _STATES:
        states, note, cap = (" ".join(name.upper().split()),), "", None
    elif (st := geo.state_of_city(name)) is not None:  # 3. documented city → state list
        states, note, cap = (st,), f"'{name}' is in {st} per the city → state list", CITY_CAP
    else:
        return None, "", None
    found = {_state_row(s, rows) for s in states}
    found.discard(None)
    if len(found) != 1:
        return None, note, cap
    return found.pop(), note, cap


def _state_row(state: str, rows: list[_Row]) -> _Row | None:
    named = [r for r in rows if state in r.states and not r.rest]
    rest = [r for r in rows if state in r.states and r.rest]
    found = named or rest
    return found[0] if found else None


def load(root: Path) -> list[Grid]:
    path = next((root / "raters" / "reliance-indusind").rglob("*.xlsx"))
    file = path.relative_to(root).as_posix()
    wb = Workbook(path)
    try:
        sheet = wb.sheet(SHEET)
        rows: list[_Row] = []
        rules: list[RateRule] = []
        zone = ""
        for r in range(3, sheet.max_row + 1):
            zone = str(sheet.value(f"A{r}") or zone).strip()
            label = sheet.value(f"B{r}")
            if not label:
                continue
            row = _parse_row(str(label), zone)
            rows.append(row)
            row_cite = XlsxCite(file, SHEET, f"A{r}:F{r}")
            for col, policy, fuel in (
                ("C", "comprehensive", _FUELS["C"]),
                ("D", "comprehensive", _FUELS["D"]),
                ("E", "saod", None),
                ("F", "satp", None),
            ):
                v = sheet.value(f"{col}{r}")
                if v is None or v is MISSING:
                    continue
                dims: list[tuple[str, DimValue]] = [("policy_type", policy), ("region", row.label)]
                if fuel is not None:
                    dims.append(("fuel", fuel))
                cell = RateCell(float(v), v, XlsxCite(file, SHEET, f"{col}{r}"))
                header = str(sheet.value(f"{col}2"))
                rules.append(
                    RateRule(
                        dims=tuple(sorted(dims)),
                        od=cell if col != "F" else None,
                        tp=cell if col == "F" else None,
                        cite=row_cite,
                        label=f"{zone} · {row.label} · {header}",
                    )
                )

        rto = wb.sheet("RTO List")
        by_code: list[MappingRow] = []
        for r in range(2, rto.max_row + 1):
            code, region, rto_zone = rto.value(f"A{r}"), rto.value(f"C{r}"), rto.value(f"E{r}")
            if not code or not region:
                continue
            hit, note, cap = _resolve_region(str(region), rows)
            if hit is None:
                continue
            cite = XlsxCite(file, "RTO List", f"A{r}:E{r}")
            by_code.append(MappingRow(str(code), hit.label, cite, raw=code, note=note, cap=cap))
            if rto_zone and _norm(rto_zone) != _norm(hit.zone):
                by_code.append(
                    MappingRow(
                        str(code),
                        f"zone {rto_zone} per 'RTO List' (grid row '{hit.label}' is {hit.zone})",
                        cite,
                        raw=code,
                    )
                )

        by_state: list[MappingRow] = []
        for state in sorted({s for row in rows for s in row.states}):
            covering = _state_row(state, rows)
            if covering is not None:
                by_state.append(
                    MappingRow(
                        state,
                        covering.label,
                        XlsxCite(file, SHEET, "B2"),
                        raw="RTO region",
                        note=f"via the RTO's state code ({state})",
                        cap=STATE_CAP,
                    )
                )

        exceptions = _tc(wb, file)
        a1 = str(sheet.value("A1"))
        return [
            Grid(
                id="reliance/pvt-car",
                insurer=INSURER,
                file=file,
                title=f"Reliance '{SHEET}'",
                vehicle_classes=frozenset({"private_car"}),
                policy_types=frozenset({"comprehensive", "saod", "satp"}),
                business_types=frozenset({"renewal", "rollover"}),
                rules=tuple(rules),
                mappings=(
                    RtoRegionTable(
                        name="Reliance RTO → region",
                        target="region",
                        by_code=tuple(by_code),
                        by_state=tuple(by_state),
                    ),
                ),
                exceptions=exceptions,
                unpublished=(
                    Unpublished(
                        "comprehensive",
                        "tp",
                        "Reliance pays on the OD premium for package policies; no TP rate is published",
                        XlsxCite(file, SHEET, "H2"),
                    ),
                ),
                effective_from=_month_year(a1),
                date_text=a1,
                date_cite=XlsxCite(file, SHEET, "A1"),
                notes=("'Make Model wise segment' is not used by this sheet (no segment dimension).",),
            )
        ]
    finally:
        wb.close()


def _tc(wb: Workbook, file: str) -> tuple[ExceptionRule, ...]:
    out: list[ExceptionRule] = []
    sheet = wb.sheet(SHEET)
    for r in range(2, sheet.max_row + 1):
        text = sheet.value(f"H{r}")
        if not text or str(text).strip().lower() == "terms & conditions":
            continue
        out.append(_rule(str(text), XlsxCite(file, SHEET, f"H{r}")))
    # Only the hygiene and synergy sections apply to private cars; the rest are CV / school bus terms.
    en = wb.sheet("Enabler, PO Guidelines & T&C")
    section = ""
    for r in range(1, en.max_row + 1):
        text = en.value(f"A{r}")
        if not text:
            continue
        t = str(text).strip()
        if t.isupper() or t.lower().startswith(("guideline", "school bus", "* terms")):
            section = t.lower()
        if not ("hygiene" in section or "synergy" in section):
            continue
        if re.match(r"^\d+\s*\.", t) or "%" in t:
            out.append(_rule(t, XlsxCite(file, en.name, f"A{r}")))
    return tuple(out)


def _rule(text: str, cite: XlsxCite) -> ExceptionRule:
    c = classify(text, "private_car")
    when: tuple[tuple[str, DimValue], ...] = ()
    m = re.search(r"<\s*(\d+)\s*CC", text, re.I)
    if c.kind == "policy_condition" and m:
        band = parse_band(f"<{m.group(1)}", "cc")
        assert band is not None
        when = (("cc", band),)
    elif c.kind == "policy_condition" and re.search(r"standa?lone\s+zd", text, re.I):
        when = (("policy_type", "zd_standalone"),)
    elif c.kind == "policy_condition" and re.search(r"tyre|rti", text, re.I):
        when = (("add_ons", frozenset({"tyre", "rti", "return to invoice"})),)
    elif c.kind == "policy_condition" and re.search(r"\bCPA\b", text):
        when = (("cpa_cover", "no"),)
    return ExceptionRule(
        c.kind, c.text, cite, effect=c.effect, percent=c.percent, when=when, components=("od",)
    )
