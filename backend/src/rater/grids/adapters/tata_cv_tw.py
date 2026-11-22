"""Tata AIG `TW` (and, in T15, `CV`) standard grids: row dimensions against RTO clusters named in row 5.

`TW`: segment (Moped / Motor Cycle / Scooter) × business type × type (Package / SATP / SAOD / All), rates as
fractions, paid on the total premium (`TW`!A2), so a package rate is reported as OD with TP unpublished
(as for the other insurers' package two-wheeler rates). "All" yields an OD rule (package / SAOD) and a TP rule
(SATP). The cluster comes from the RTO location printed on the policy (`General Guidelines`!C10).
"""

import re
from datetime import date
from pathlib import Path

from openpyxl.utils import get_column_letter

from rater.citations import XlsxCite
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

INSURER = "Tata AIG"
_BUSINESS = {"brand new": "new", "renewal": "renewal", "rollover": "rollover"}
_TW_TYPE = {"motor cycle": "motorcycle", "scooter": "scooter", "moped": "moped"}
_TYPES: dict[str, list[str]] = {
    "package": ["comprehensive"],
    "saod": ["saod"],
    "satp": ["satp"],
    "all": ["comprehensive", "saod", "satp"],
}


def _date(text: str) -> date | None:
    m = re.search(r"(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]{3})[a-z]*'?(\d{2})", text)
    months = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
    if not m or m.group(2).lower() not in months:
        return None
    return date(2000 + int(m.group(3)), months.index(m.group(2).lower()) + 1, int(m.group(1)))


def _guidelines(wb: Workbook, file: str, product: str) -> list[ExceptionRule]:
    gg = wb.sheet("General Guidelines")
    out = []
    for r in range(4, gg.max_row + 1):
        text = gg.value(f"C{r}")
        if text:
            k = classify(str(text), product)
            out.append(
                ExceptionRule(
                    k.kind, k.text, XlsxCite(file, gg.name, f"C{r}"), effect=k.effect, percent=k.percent
                )
            )
    return out


def load_tw(root: Path) -> Grid:
    path = next((root / "raters" / "tata-aig").rglob("*.xlsx"))
    file = path.relative_to(root).as_posix()
    wb = Workbook(path)
    try:
        sheet = wb.sheet("TW")
        clusters = [
            (get_column_letter(c), str(sheet.value(f"{get_column_letter(c)}5")).strip())
            for c in range(5, sheet.max_column + 1)
            if sheet.value(f"{get_column_letter(c)}5")
        ]
        rules: list[RateRule] = []
        for r in range(6, sheet.max_row + 1):
            seg, business, kind = sheet.value(f"B{r}"), sheet.value(f"C{r}"), sheet.value(f"D{r}")
            if not seg:
                continue
            s, b, k = (str(x).strip().lower() for x in (seg, business, kind))
            if s not in _TW_TYPE or b not in _BUSINESS or k not in _TYPES:
                raise ValueError(f"Tata AIG 'TW' row {r}: unknown {seg!r}/{business!r}/{kind!r}")
            base: list[tuple[str, DimValue]] = [("business_type", _BUSINESS[b]), ("tw_type", _TW_TYPE[s])]
            policy_types = _TYPES[k]
            od_types = [p for p in policy_types if p != "satp"]
            for col, cluster in clusters:
                v = sheet.value(f"{col}{r}")
                if not isinstance(v, int | float) or v is MISSING:
                    continue
                cell = RateCell(round(float(v) * 100, 6), v, XlsxCite(file, "TW", f"{col}{r}"))
                row_cite = XlsxCite(file, "TW", f"B{r}:D{r}")
                label = f"{seg} · {business} · {kind} · {cluster}"
                if od_types:
                    pt: DimValue = od_types[0] if len(od_types) == 1 else frozenset(od_types)
                    rules.append(
                        RateRule(
                            tuple(sorted(base + [("cluster", cluster), ("policy_type", pt)])),
                            cell,
                            None,
                            row_cite,
                            label,
                        )
                    )
                if "satp" in policy_types:
                    rules.append(
                        RateRule(
                            tuple(sorted(base + [("cluster", cluster), ("policy_type", "satp")])),
                            None,
                            cell,
                            row_cite,
                            label,
                        )
                    )
        exceptions = [
            ExceptionRule(
                classify(str(sheet.value(f"A{r}")), "two_wheeler").kind,
                " ".join(str(sheet.value(f"A{r}")).split()),
                XlsxCite(file, "TW", f"A{r}"),
            )
            for r in (2, 3)
            if sheet.value(f"A{r}")
        ]
        exceptions += _guidelines(wb, file, "two_wheeler")
        a1 = str(sheet.value("A1"))
        return Grid(
            id="tata-aig/TW",
            insurer=INSURER,
            file=file,
            title="Tata AIG 'TW'",
            vehicle_classes=frozenset({"two_wheeler", "scooter", "motorcycle", "moped"}),
            policy_types=frozenset({"comprehensive", "saod", "satp"}),
            rules=tuple(rules),
            mappings=(
                MappingTable(
                    name="Tata AIG RTO location → TW cluster (General Guidelines C10: RTO mapped on policy)",
                    source="rto_location",
                    target="cluster",
                    rows=tuple(MappingRow(n, n, XlsxCite(file, "TW", f"{c}5"), raw=n) for c, n in clusters),
                ),
            ),
            exceptions=tuple(exceptions),
            unpublished=(
                Unpublished(
                    "comprehensive",
                    "tp",
                    "Tata AIG pays two-wheeler package policies on the "
                    "total premium (TW A2); one rate is published, reported as OD",
                    XlsxCite(file, "TW", "A2"),
                ),
            ),
            effective_from=_date(a1),
            date_text=a1,
            date_cite=XlsxCite(file, "TW", "A1"),
        )
    finally:
        wb.close()


def load(root: Path) -> list[Grid]:
    return [load_tw(root)]
