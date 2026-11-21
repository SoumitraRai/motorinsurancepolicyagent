"""Go Digit private car: `4W SATP` (cluster × fuel/CC segment × age → Max CD2 on TP), `4W New Business 1+3`
(cluster × make group → CD2), and the `4W  RTO` RTO → cluster map (column C for TP, column D for package).
"""

import re
from pathlib import Path

from rater.citations import XlsxCite
from rater.grids.bands import parse_band
from rater.grids.makes import canonical_make
from rater.grids.model import (
    DimValue,
    ExceptionRule,
    Grid,
    MappingRow,
    MappingTable,
    NotIn,
    RateCell,
    RateRule,
    Unpublished,
)
from rater.grids.textrules import classify
from rater.grids.xlsx import MISSING, Sheet, Workbook
from rater.resolve.confidence import Cap

INSURER = "Go Digit"
_FUELS = {"petrol": "petrol", "diesel": "diesel", "cng": "cng"}


def _pct(value: object) -> float:
    """Go Digit stores rates as fractions (0.295 = 29.5%)."""
    v = float(value)  # type: ignore[arg-type]
    return round(v * 100, 6) if v <= 1 else v


def _clusters(text: str) -> list[str]:
    """`AP TS_Good1/Good2` → [`AP TS_Good1`, `AP TS_Good2`]; `Delhi/NCR` → [`Delhi`, `NCR`]."""
    parts = [p.strip() for p in str(text).split("/")]
    first = parts[0]
    prefix = first.rsplit("_", 1)[0] + "_" if "_" in first else ""
    return [first] + [p if ("_" in p or not prefix) else prefix + p for p in parts[1:]]


def _segment(text: str) -> tuple[DimValue, DimValue] | None:
    m = re.fullmatch(r"\s*(petrol|diesel|cng)\s*(.*?)\s*", str(text), re.I)
    if not m:
        return None
    band = parse_band(m.group(2) or "All", "cc")
    return (_FUELS[m.group(1).lower()], band) if band else None


def _rto_table(sheet: Sheet, file: str, column: str, target: str) -> MappingTable:
    rows = []
    for r in range(3, sheet.max_row + 1):
        code, value = sheet.value(f"B{r}"), sheet.value(f"{column}{r}")
        if code and value and value is not MISSING:
            rows.append(
                MappingRow(
                    str(code), str(value).strip(), XlsxCite(file, sheet.name, f"B{r}:{column}{r}"), raw=code
                )
            )
    header = sheet.value(f"{column}2")
    return MappingTable(
        name=f"Go Digit RTO → {header} cluster", source="rto", target=target, rows=tuple(rows)
    )


def _satp(wb: Workbook, file: str) -> Grid:
    sheet = wb.sheet("4W SATP")
    rules: list[RateRule] = []
    exceptions: list[ExceptionRule] = []
    for r in range(3, sheet.max_row + 1):
        cluster, seg, age, cd2, note = (sheet.value(f"{c}{r}") for c in "BCDEF")
        if not cluster:
            continue
        parsed = _segment(seg)
        age_band = parse_band(str(age), "years")
        if parsed is None or age_band is None or cd2 is None or cd2 is MISSING:
            raise ValueError(
                f"Go Digit '4W SATP' row {r}: unreadable segment/age/rate {seg!r} {age!r} {cd2!r}"
            )
        fuel, cc = parsed
        for c in _clusters(str(cluster)):
            dims: tuple[tuple[str, DimValue], ...] = (
                ("age", age_band),
                ("cc", cc),
                ("cluster", c),
                ("fuel", fuel),
            )
            rules.append(
                RateRule(
                    dims=dims,
                    od=None,
                    tp=RateCell(_pct(cd2), cd2, XlsxCite(file, sheet.name, f"E{r}"), label="Max CD2"),
                    cite=XlsxCite(file, sheet.name, f"B{r}:F{r}"),
                    label=f"{c} · {seg} · age {age}",
                )
            )
            if "decline" in c.lower():
                exceptions.append(
                    ExceptionRule(
                        "policy_condition",
                        str(cluster),
                        XlsxCite(file, sheet.name, f"B{r}"),
                        effect="decline",
                        when=dims,
                    )
                )
            if note:
                k = classify(str(note), "private_car")
                exceptions.append(
                    ExceptionRule(
                        k.kind,
                        k.text,
                        XlsxCite(file, sheet.name, f"F{r}"),
                        effect=k.effect,
                        percent=k.percent,
                        when=dims,
                    )
                )
    rto = wb.sheet("4W  RTO")
    return Grid(
        id="godigit/4W SATP",
        insurer=INSURER,
        file=file,
        title="Go Digit '4W SATP'",
        vehicle_classes=frozenset({"private_car"}),
        policy_types=frozenset({"satp"}),
        rules=tuple(rules),
        mappings=(_rto_table(rto, file, "C", "cluster"),),
        exceptions=tuple(exceptions),
    )


def _new_business(wb: Workbook, file: str) -> Grid:
    sheet = wb.sheet("4W New Business 1+3")
    groups: dict[str, list[str]] = {}
    for col in "BCDEFGH":
        header = str(sheet.value(f"{col}3"))
        groups[col] = [canonical_make(re.sub(r"^HEV-", "", m.strip(), flags=re.I)) for m in header.split(",")]
    listed = sorted({m for col, ms in groups.items() for m in ms if m != "OTHERS"})

    rules: list[RateRule] = []
    for r in range(4, sheet.max_row + 1):
        cluster = sheet.value(f"A{r}")
        if not cluster:
            continue
        for col in "BCDEFGHI":
            v = sheet.value(f"{col}{r}")
            if v is None or v is MISSING:
                continue
            cell = RateCell(_pct(v), v, XlsxCite(file, sheet.name, f"{col}{r}"), label="CD2")
            row_cite = XlsxCite(file, sheet.name, f"A{r}:I{r}")
            base: list[tuple[str, DimValue]] = [("cluster", str(cluster).strip())]
            if col == "I":
                rules.append(
                    RateRule(
                        tuple(sorted(base + [("od_term_years", "3")])),
                        cell,
                        None,
                        row_cite,
                        f"{cluster} · 3+3 · all makes",
                    )
                )
                continue
            makes = [m for m in groups[col] if m != "OTHERS"]
            term: list[tuple[str, DimValue]] = [("od_term_years", "1")]
            rules.append(
                RateRule(
                    tuple(sorted(base + term + [("make", frozenset(makes))])),
                    cell,
                    None,
                    row_cite,
                    f"{cluster} · 1+3 · {sheet.value(f'{col}3')}",
                )
            )
            if "OTHERS" in groups[col]:
                rules.append(
                    RateRule(
                        tuple(sorted(base + term + [("make", NotIn(frozenset(listed)))])),
                        cell,
                        None,
                        row_cite,
                        f"{cluster} · 1+3 · other makes",
                    )
                )
    rto = wb.sheet("4W  RTO")
    b2 = XlsxCite(file, sheet.name, "B2")
    return Grid(
        id="godigit/4W New Business 1+3",
        insurer=INSURER,
        file=file,
        title="Go Digit '4W New Business 1+3'",
        vehicle_classes=frozenset({"private_car"}),
        policy_types=frozenset({"comprehensive"}),
        business_types=frozenset({"new"}),
        rules=tuple(rules),
        mappings=(_rto_table(rto, file, "D", "cluster"),),
        unpublished=(
            Unpublished(
                "comprehensive",
                "tp",
                "Go Digit's new-business grid publishes one CD2 rate "
                "(applied here to OD); no separate TP rate is published",
                b2,
            ),
        ),
        caps=(
            Cap(
                "medium",
                "Go Digit new-business CD2 does not state which premium it applies to; treated as OD",
            ),
        ),
    )


def load(root: Path) -> list[Grid]:
    path = next((root / "raters" / "godigit").rglob("*.xlsx"))
    file = path.relative_to(root).as_posix()
    wb = Workbook(path)
    try:
        return [_satp(wb, file), _new_business(wb, file)]
    finally:
        wb.close()
