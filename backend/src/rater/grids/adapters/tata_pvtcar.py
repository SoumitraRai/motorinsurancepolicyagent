"""Tata AIG `Pvtcar` standard grid: segment × business type × fuel × section × NCB × add-on (columns G–L)
against 55 RTO clusters (columns M–BO, named in row 5). Rates are fractions of the OD premium for
Package/SAOD and of the net premium for SATP (`Pvtcar`!F2, `General Guidelines`!C7).

The cluster comes from the RTO location printed on the policy (`General Guidelines`!C10). The workbook has
no make/model → segment table (checked all 7 sheets, hidden ones included), so a policy that doesn't print
its segment cannot be rated (spec C8).
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
SHEET = "Pvtcar"
_BUSINESS = {"brand new": "new", "renewal": "renewal", "rollover": "rollover"}
_SECTION = {"package": "comprehensive", "saod": "saod", "satp": "satp"}
# "Other Than Diesel" is read as fuels the sheet doesn't list separately (CNG and Electric have their own
# rows), so a CNG car never matches two rows. README assumption.
_FUEL: dict[str, frozenset[str]] = {
    "diesel": frozenset({"diesel"}),
    "cng": frozenset({"cng"}),
    "electric": frozenset({"electric"}),
    "other than diesel": frozenset({"petrol", "lpg", "hybrid"}),
}
_YESNO = {"yes": "yes", "no": "no"}
_NCB = {"yes": "ncb", "no": "no_ncb"}
C8 = (
    "The Tata AIG workbook has no make/model → segment table (all 7 sheets checked, hidden ones included), "
    "and the policy does not print a Tata AIG segment."
)


def _date(text: str) -> date | None:
    m = re.search(r"(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]{3})[a-z]*'?(\d{2})", text)
    months = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
    if not m or m.group(2).lower() not in months:
        return None
    return date(2000 + int(m.group(3)), months.index(m.group(2).lower()) + 1, int(m.group(1)))


def load(root: Path) -> list[Grid]:
    path = next((root / "raters" / "tata-aig").rglob("*.xlsx"))
    file = path.relative_to(root).as_posix()
    wb = Workbook(path)
    try:
        sheet = wb.sheet(SHEET)
        clusters = []
        for c in range(13, sheet.max_column + 1):
            col = get_column_letter(c)
            name = sheet.value(f"{col}5")
            if name and col <= "BO":  # BQ/BR are helper columns ("a", "Concat")
                clusters.append((col, str(name).strip()))

        rules: list[RateRule] = []
        segments: dict[str, XlsxCite] = {}
        for r in range(6, sheet.max_row + 1):
            seg = sheet.value(f"G{r}")
            if not seg or sheet.is_aggregate(f"M{r}"):
                continue
            business, fuel, section, ncb, add_on = (
                str(sheet.value(f"{c}{r}")).strip().lower() for c in "HIJKL"
            )
            if business not in _BUSINESS or fuel not in _FUEL or section not in _SECTION:
                raise ValueError(f"Tata AIG '{SHEET}' row {r}: unknown {business!r}/{fuel!r}/{section!r}")
            segments.setdefault(str(seg).strip(), XlsxCite(file, SHEET, f"G{r}"))
            dims: list[tuple[str, DimValue]] = [
                ("business_type", _BUSINESS[business]),
                ("fuel", _FUEL[fuel]),
                ("policy_type", _SECTION[section]),
                ("tata_segment", str(seg).strip()),
            ]
            if ncb in _NCB:
                dims.append(("ncb_flag", _NCB[ncb]))
            if add_on in _YESNO:
                dims.append(("has_add_ons", _YESNO[add_on]))
            for col, cluster in clusters:
                v = sheet.value(f"{col}{r}")
                if v is None or v is MISSING:
                    continue
                cell = RateCell(round(float(v) * 100, 6), v, XlsxCite(file, SHEET, f"{col}{r}"))
                satp = section == "satp"
                rules.append(
                    RateRule(
                        dims=tuple(sorted(dims + [("cluster", cluster)])),
                        od=None if satp else cell,
                        tp=cell if satp else None,
                        cite=XlsxCite(file, SHEET, f"G{r}:L{r}"),
                        label=f"{seg} · {sheet.value(f'H{r}')} · {sheet.value(f'I{r}')} · "
                        f"{sheet.value(f'J{r}')} · "
                        f"NCB {sheet.value(f'K{r}')} · add-on {sheet.value(f'L{r}')} · {cluster}",
                    )
                )

        cluster_table = MappingTable(
            name="Tata AIG RTO location → cluster (General Guidelines C10: RTO mapped on policy)",
            source="rto_location",
            target="cluster",
            rows=tuple(
                MappingRow(name, name, XlsxCite(file, SHEET, f"{col}5"), raw=name) for col, name in clusters
            ),
        )
        segment_table = MappingTable(
            name="Tata AIG segment",
            source="segment",
            target="tata_segment",
            rows=tuple(MappingRow(s, s, c, raw=s) for s, c in segments.items()),
            if_missing="unsupported",
            missing_reason=C8,
        )

        gg = wb.sheet("General Guidelines")
        exceptions = []
        for r in range(4, gg.max_row + 1):
            text = gg.value(f"C{r}")
            if text:
                k = classify(str(text), "private_car")
                exceptions.append(
                    ExceptionRule(
                        k.kind, k.text, XlsxCite(file, gg.name, f"C{r}"), effect=k.effect, percent=k.percent
                    )
                )
        f1, f2 = str(sheet.value("F1")), XlsxCite(file, SHEET, "F2")
        return [
            Grid(
                id="tata-aig/Pvtcar",
                insurer=INSURER,
                file=file,
                title=f"Tata AIG '{SHEET}'",
                vehicle_classes=frozenset({"private_car"}),
                policy_types=frozenset({"comprehensive", "saod", "satp"}),
                rules=tuple(rules),
                mappings=(segment_table, cluster_table),
                exceptions=tuple(exceptions),
                unpublished=(
                    Unpublished(
                        "comprehensive",
                        "tp",
                        "Tata AIG pays package policies on the OD premium "
                        "(Pvtcar F2); no TP rate is published for them",
                        f2,
                    ),
                ),
                effective_from=_date(f1),
                date_text=f1,
                date_cite=XlsxCite(file, SHEET, "F1"),
                notes=("Row 4 marks each cluster DM or HOM; the meaning is not stated, so it is not used.",),
            )
        ]
    finally:
        wb.close()
