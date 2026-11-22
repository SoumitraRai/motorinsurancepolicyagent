"""Reliance two-wheeler `TW SCOOTER GRID`: region × Fresh 1+5 / Fresh 5+5 / Comp / SA OD / STP, with T&C in
column K. Regions resolve through the shared Reliance `RTO List` logic (`reliance_pvtcar.build_region_table`).

Scope from the sheet's own T&C (K5, "Grid Not applicable for Bike Comp (1+1 / 1+5 / 5+5) & STP"): motorcycles
get only the SA OD column; every other column is for scooters.
"""

import re
from pathlib import Path

from rater.citations import XlsxCite
from rater.grids.adapters.reliance_pvtcar import _month_year, build_region_table, parse_region_row
from rater.grids.model import (
    DimValue,
    ExceptionRule,
    Grid,
    MappingRow,
    MappingTable,
    RateCell,
    RateRule,
    Unpublished,
)
from rater.grids.textrules import classify
from rater.grids.xlsx import MISSING, Workbook

INSURER = "Reliance"
SHEET = "TW SCOOTER GRID"
_COLUMNS: dict[str, list[tuple[str, DimValue]]] = {
    "C": [
        ("policy_type", "comprehensive"),
        ("business_type", "new"),
        ("od_term_years", "1"),
        ("tw_type", "scooter"),
    ],
    "D": [
        ("policy_type", "comprehensive"),
        ("business_type", "new"),
        ("od_term_years", "5"),
        ("tw_type", "scooter"),
    ],
    "E": [
        ("policy_type", "comprehensive"),
        ("business_type", frozenset({"renewal", "rollover"})),
        ("tw_type", "scooter"),
    ],
    "F": [("policy_type", "saod")],
    "G": [("policy_type", "satp"), ("tw_type", "scooter")],
}
_FRESH: tuple[tuple[str, DimValue], ...] = (("business_type", "new"),)
_MISSPELT = {"MANGOLORE": "MANGALORE"}


def _city_table(wb: Workbook, file: str) -> MappingTable:
    rto = wb.sheet("RTO List")
    rows = []
    for r in range(2, rto.max_row + 1):
        code, city = rto.value(f"A{r}"), rto.value(f"C{r}")
        if code and city:
            rows.append(
                MappingRow(
                    str(code),
                    " ".join(str(city).upper().split()),
                    XlsxCite(file, "RTO List", f"A{r}:C{r}"),
                    raw=code,
                )
            )
    return MappingTable(
        name="Reliance RTO → RTO List region name",
        source="rto",
        target="reliance_city",
        rows=tuple(rows),
        optional=True,
    )


def _tc(sheet_text: str, cite: XlsxCite, in_contest: bool) -> list[ExceptionRule]:
    if in_contest:
        return [ExceptionRule("broker_side", sheet_text, cite)]
    k = classify(sheet_text, "two_wheeler")
    if k.kind != "policy_condition":
        return [ExceptionRule(k.kind, k.text, cite)]
    low = sheet_text.lower()
    base = ExceptionRule(k.kind, k.text, cite, effect=k.effect, percent=k.percent, components=("od",))
    if "ev makes" in low:
        return [_with(base, _FRESH + (("fuel", "electric"),))]
    if "yamaha" in low or "hmc" in low:
        return [_with(base, _FRESH + (("make", frozenset({"YAMAHA", "HERO MOTOCORP"})),))]
    m = re.search(r"rto regions?:\s*(.+?)\s*-\s*po", sheet_text, re.I)
    if m:
        named, out = [], []
        for part in re.split(r"\s*,\s*", m.group(1)):
            if (
                "excluding" in part.lower()
            ):  # "West Bengal (Excluding Kolkata)": the RTO List names Kolkata apart
                state = part.split("(")[0].strip().upper()
                out.append(_with(base, _FRESH + (("reliance_city", state),)))
            else:
                named.append(_MISSPELT.get(part.strip().upper(), part.strip().upper()))
        if named:
            out.insert(0, _with(base, _FRESH + (("reliance_city", frozenset(named)),)))
        return out
    return [base]


def _with(rule: ExceptionRule, when: tuple[tuple[str, DimValue], ...]) -> ExceptionRule:
    return ExceptionRule(rule.kind, rule.text, rule.cite, rule.effect, rule.percent, when, rule.components)


def load(root: Path) -> list[Grid]:
    path = next((root / "raters" / "reliance-indusind").rglob("*.xlsx"))
    file = path.relative_to(root).as_posix()
    wb = Workbook(path)
    try:
        sheet = wb.sheet(SHEET)
        rows, rules = [], []
        zone = ""
        for r in range(3, sheet.max_row + 1):
            zone = str(sheet.value(f"A{r}") or zone).strip()
            label = sheet.value(f"B{r}")
            if not label:
                continue
            row = parse_region_row(str(label), zone, SHEET)
            rows.append(row)
            for col, dims in _COLUMNS.items():
                v = sheet.value(f"{col}{r}")
                if not isinstance(v, int | float) or v is MISSING:
                    continue
                cell = RateCell(float(v), v, XlsxCite(file, SHEET, f"{col}{r}"))
                tp = col == "G"
                rules.append(
                    RateRule(
                        dims=tuple(sorted(dims + [("region", row.label)], key=lambda d: d[0])),
                        od=None if tp else cell,
                        tp=cell if tp else None,
                        cite=XlsxCite(file, SHEET, f"A{r}:G{r}"),
                        label=f"{zone} · {row.label} · {sheet.value(f'{col}2')}",
                    )
                )
        exceptions: list[ExceptionRule] = []
        in_contest = False
        for r in range(2, sheet.max_row + 1):
            text = sheet.value(f"K{r}")
            if not text:
                continue
            in_contest = in_contest or "contest" in str(text).lower()
            exceptions.extend(_tc(str(text).strip(), XlsxCite(file, SHEET, f"K{r}"), in_contest))
        a1 = str(sheet.value("A1"))
        return [
            Grid(
                id="reliance/tw-scooter",
                insurer=INSURER,
                file=file,
                title=f"Reliance '{SHEET}'",
                vehicle_classes=frozenset({"two_wheeler", "scooter", "motorcycle"}),
                policy_types=frozenset({"comprehensive", "saod", "satp"}),
                rules=tuple(rules),
                mappings=(
                    build_region_table(wb, file, rows, SHEET, "Reliance RTO → TW region"),
                    _city_table(wb, file),
                ),
                exceptions=tuple(exceptions),
                unpublished=(
                    Unpublished(
                        "comprehensive",
                        "tp",
                        "Reliance's two-wheeler grid publishes one rate for "
                        "package policies; no TP rate is published",
                        XlsxCite(file, SHEET, "E2"),
                    ),
                ),
                effective_from=_month_year(a1),
                date_text=a1,
                date_cite=XlsxCite(file, SHEET, "A1"),
            )
        ]
    finally:
        wb.close()
