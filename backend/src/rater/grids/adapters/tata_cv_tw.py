"""Tata AIG `TW` and `CV` standard grids: row dimensions against RTO clusters named in row 5.

`TW`: segment (Moped / Motor Cycle / Scooter) × business type × type (Package / SATP / SAOD / All), rates as
fractions, paid on the total premium (`TW`!A2), so a package rate is reported as OD with TP unpublished
(as for the other insurers' package two-wheeler rates). "All" yields an OD rule (package / SAOD) and a TP rule
(SATP). The cluster comes from the RTO location printed on the policy (`General Guidelines`!C10).

`CV`: segment × fuel × Package / SATP × vehicle age category, "All % on Net Premium" (`CV`!A2), so a package
rate is reported as OD with TP unpublished. Readings (README assumptions):
- GCV bands are GVW in tonnes, "> a <= b" = (a, b]. "Brand New" = new business; ">=1<=6" and ">6" are the
  vehicle's age in years. "Other Than Diesel" = petrol, LPG or hybrid (CNG and Electric have their rows).
- "PCV 4W" = up to 11 seats (the bus rows start at 12): "School" a school bus, "Non School" a taxi.
  "PCV Bus Non School" = a staff bus, or a passenger vehicle of 12+ seats. "Harvester" = a misc vehicle
  whose body type says harvester; "Misc" = the other misc vehicles.
- "Trade Road Risk" and "Trailer" are not vehicle classes the policy facts carry: not read (noted).
- Row 4 (DM / HOM) and the helper columns after the clusters don't change a rate.
"""

import re
from datetime import date
from pathlib import Path

from openpyxl.utils import get_column_letter

from rater.citations import XlsxCite
from rater.grids.bands import Band
from rater.grids.model import (
    ContainsAny,
    DimValue,
    ExceptionRule,
    Grid,
    MappingRow,
    MappingTable,
    NotContainsAny,
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


INF = float("inf")
HARVESTER = frozenset({"HARVESTER"})
_CV_FUEL: dict[str, DimValue | None] = {
    "all": None,
    "diesel": "diesel",
    "cng": "cng",
    "electric": "electric",
    "other than diesel": frozenset({"petrol", "lpg", "hybrid"}),
}
_CV_AGE: dict[str, tuple[str, DimValue] | None] = {
    "brand new": ("business_type", "new"),
    ">=1<=6": ("age", Band(1, 6, True, True, "years", ">=1<=6")),
    ">6": ("age", Band(6, INF, False, True, "years", ">6")),
    "all": None,
}
_NOT_READ = ("trade road risk", "trailer")


def _seats(lo: float, hi: float, label: str) -> tuple[str, DimValue]:
    return ("seating_capacity", Band(lo, hi, True, True, "seats", label))


def _cv_segment(text: str) -> list[tuple[str, DimValue]] | None:
    """Rule dimensions of a `CV` segment, or None for a segment not read."""
    t = " ".join(text.lower().split())
    if t in _NOT_READ:
        return None
    if m := re.fullmatch(r"gcv\s*(?:>\s*(\d+(?:\.\d+)?))?\s*(?:<=\s*(\d+(?:\.\d+)?))?", t):
        lo = float(m[1]) if m[1] else 0.0
        hi = float(m[2]) if m[2] else INF
        return [("vehicle_class", "gcv"), ("gvw_t", Band(lo, hi, not m[1], True, "t", text.strip()))]
    if m := re.fullmatch(r"pcv bus (non school|school) (?:(\d+) to (\d+)|> (\d+))", t):
        seats = _seats(int(m[2]), int(m[3]), f"{m[2]}-{m[3]}") if m[2] else (
            "seating_capacity", Band(int(m[4]), INF, False, True, "seats", f"> {m[4]}")
        )  # fmt: skip
        vc: DimValue = "school_bus" if m[1] == "school" else frozenset({"staff_bus", "pcv_taxi"})
        return [("vehicle_class", vc), seats]
    fixed: dict[str, list[tuple[str, DimValue]]] = {
        "gcv 3w": [("vehicle_class", "gcv_3w")],
        "pcv 2w": [("vehicle_class", "pcv_2w")],
        "pcv 3w": [("vehicle_class", "pcv_3w")],
        "pcv 4w non school": [("vehicle_class", "pcv_taxi"), _seats(0, 11, "4W")],
        "pcv 4w school": [("vehicle_class", "school_bus"), _seats(0, 11, "4W")],
        "misc": [("vehicle_class", "misc_d"), ("body_type", NotContainsAny(HARVESTER))],
        "harvester": [("vehicle_class", "misc_d"), ("body_type", ContainsAny(HARVESTER))],
        "tractor": [("vehicle_class", "tractor")],
    }
    if t not in fixed:
        raise ValueError(f"Tata AIG 'CV': unknown segment {text!r}")
    return fixed[t]


def load_cv(root: Path) -> Grid:
    path = next((root / "raters" / "tata-aig").rglob("*.xlsx"))
    file = path.relative_to(root).as_posix()
    wb = Workbook(path)
    try:
        sheet = wb.sheet("CV")
        clusters = [
            (get_column_letter(c), str(sheet.value(f"{get_column_letter(c)}5")).strip())
            for c in range(6, sheet.max_column + 1)
            if sheet.value(f"{get_column_letter(c)}5")
            and str(sheet.value(f"{get_column_letter(c)}5")).strip() != "a"
        ]
        rules: list[RateRule] = []
        skipped: set[str] = set()
        for r in range(6, sheet.max_row + 1):
            seg, fuel, kind, age = (sheet.value(f"{c}{r}") for c in "BCDE")
            if not seg:
                continue
            dims = _cv_segment(str(seg))
            if dims is None:
                skipped.add(str(seg).strip())
                continue
            f, k, a = (" ".join(str(x).lower().split()) for x in (fuel, kind, age))
            if f not in _CV_FUEL or k not in ("package", "satp") or a not in _CV_AGE:
                raise ValueError(f"Tata AIG 'CV' row {r}: unknown {fuel!r}/{kind!r}/{age!r}")
            base = list(dims)
            if _CV_FUEL[f] is not None:
                base.append(("fuel", _CV_FUEL[f]))  # type: ignore[arg-type]
            if _CV_AGE[a] is not None:
                base.append(_CV_AGE[a])  # type: ignore[arg-type]
            policy = "comprehensive" if k == "package" else "satp"
            row_cite = XlsxCite(file, "CV", f"B{r}:E{r}")
            for col, cluster in clusters:
                v = sheet.value(f"{col}{r}")
                if not isinstance(v, int | float) or v is MISSING:
                    continue
                cell = RateCell(round(float(v) * 100, 6), v, XlsxCite(file, "CV", f"{col}{r}"))
                when = tuple(
                    sorted([*base, ("cluster", cluster), ("policy_type", policy)], key=lambda d: d[0])
                )
                label = f"{seg} · {fuel} · {kind} · {age} · {cluster}"
                od, tp = (cell, None) if policy == "comprehensive" else (None, cell)
                rules.append(RateRule(when, od, tp, row_cite, label))
        exceptions = [
            ExceptionRule(
                classify(str(sheet.value(f"A{r}")), "gcv").kind,
                " ".join(str(sheet.value(f"A{r}")).split()),
                XlsxCite(file, "CV", f"A{r}"),
            )
            for r in (2, 3)
            if sheet.value(f"A{r}")
        ]
        exceptions += _guidelines(wb, file, "gcv")
        a1 = str(sheet.value("A1"))
        classes = frozenset(
            v
            for rule in rules
            for d, w in rule.dims
            if d == "vehicle_class"
            for v in ([w] if isinstance(w, str) else w)  # type: ignore[union-attr]
        )
        return Grid(
            id="tata-aig/CV",
            insurer=INSURER,
            file=file,
            title="Tata AIG 'CV'",
            vehicle_classes=classes,
            policy_types=frozenset({"comprehensive", "satp"}),
            rules=tuple(rules),
            mappings=(
                MappingTable(
                    name="Tata AIG RTO location → CV cluster (General Guidelines C10: RTO mapped on policy)",
                    source="rto_location",
                    target="cluster",
                    rows=tuple(MappingRow(n, n, XlsxCite(file, "CV", f"{c}5"), raw=n) for c, n in clusters),
                ),
            ),
            exceptions=tuple(exceptions),
            unpublished=(
                Unpublished(
                    "comprehensive",
                    "tp",
                    "Tata AIG pays CV on the net premium (CV A2); one package rate is published, "
                    "reported as OD",
                    XlsxCite(file, "CV", "A2"),
                ),
            ),
            effective_from=_date(a1),
            date_text=a1,
            date_cite=XlsxCite(file, "CV", "A1"),
            notes=tuple(
                f"'CV' segment '{s}' is not read: no policy vehicle class matches it."
                for s in sorted(skipped)
            ),
        )
    finally:
        wb.close()


def load(root: Path) -> list[Grid]:
    return [load_tw(root), load_cv(root)]
