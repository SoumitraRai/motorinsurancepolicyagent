"""Go Digit two-wheelers: `TW 1+1 & SATP`, `TW 1+5`, `2W Grid 5+5`, `TW SAOD with Flexi Options`, and the
`2W RTO's` RTO → cluster map (column C for 1+1 & SATP, D for 1+5 & 5+5, E for SAOD).

- Segments (scooter / motorcycle × CC band × make group, or EV power) are parsed by `twsegments`.
- "Max CD2" is the broker payout. CD1 columns are not brokerage and are not used (README assumption).
- A text code where a rate should be ("D", "MISP") gives no rate. Its meaning is not stated, so a policy
  in that row is refused with the code quoted.
- Package rates (1+1, 1+5, 5+5) publish one CD2 whose basis is "Slab Net 5" or "OD plus Add on"
  (`Formula Type`). It is reported as the OD rate with that basis in the reason, and TP is unpublished
  (confidence capped), as for Go Digit's 4W new-business grid.
"""

from pathlib import Path

from rater.citations import XlsxCite
from rater.grids.adapters.godigit_4w import _pct
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
from rater.grids.twsegments import parse_tw_segment
from rater.grids.xlsx import MISSING, Sheet, Workbook
from rater.resolve.confidence import Cap

INSURER = "Go Digit"
CLASSES = frozenset({"two_wheeler", "scooter", "motorcycle"})
CODES = ("D", "MISP")
PKG_CAP = Cap(
    "medium", "Go Digit two-wheeler CD2 is one rate on a stated basis; reported as OD, TP unpublished"
)


def _rto(wb: Workbook, file: str, column: str, label: str) -> MappingTable:
    sheet = wb.sheet("2W RTO's")
    rows = []
    for r in range(3, sheet.max_row + 1):
        code, value = sheet.value(f"B{r}"), sheet.value(f"{column}{r}")
        if code and value and value is not MISSING:
            rows.append(
                MappingRow(
                    str(code), str(value).strip(), XlsxCite(file, sheet.name, f"B{r}:{column}{r}"), raw=code
                )
            )
    return MappingTable(
        name=f"Go Digit 2W RTO → cluster ({label})", source="rto", target="cluster", rows=tuple(rows)
    )


def _siblings(sheet: Sheet, start: int, cluster_col: str, seg_col: str) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for r in range(start, sheet.max_row + 1):
        c, s = sheet.value(f"{cluster_col}{r}"), sheet.value(f"{seg_col}{r}")
        if c and s:
            out.setdefault(str(c).strip(), []).append(str(s))
    return out


def _cluster_dims(cluster: str) -> list[tuple[str, DimValue]]:
    return [] if cluster.lower() == "all" else [("cluster", cluster)]


def _make_dims(text: str | None, row_makes_in_cluster: set[str]) -> list[list[tuple[str, DimValue]]]:
    """`1+5`/`5+5` make column: "HONDA", "BAJAJ/HONDA", "Others", "YAMAHA/Others"."""
    from rater.grids.makes import canonical_make
    from rater.grids.model import NotIn

    if not text:
        return [[]]
    parts = [canonical_make(p.strip()) for p in str(text).split("/") if p.strip()]
    named = [p for p in parts if p != "OTHERS"]
    alts: list[list[tuple[str, DimValue]]] = []
    if named:
        alts.append([("make", frozenset(named))])
    if "OTHERS" in parts:
        alts.append([("make", NotIn(frozenset(row_makes_in_cluster - set(named))))])
    return alts


def _code_exception(code: str, cite: XlsxCite, when: tuple[tuple[str, DimValue], ...]) -> ExceptionRule:
    return ExceptionRule(
        "policy_condition",
        f"The grid gives '{code}' instead of a rate (meaning not stated)",
        cite,
        effect="decline",
        when=when,
    )


def _one_plus_one(wb: Workbook, file: str) -> list[Grid]:
    sheet = wb.sheet("TW 1+1 & SATP")
    sibs = _siblings(sheet, 5, "B", "C")
    pkg: list[RateRule] = []
    satp: list[RateRule] = []
    exc_pkg: list[ExceptionRule] = []
    exc_satp: list[ExceptionRule] = []
    for r in range(5, sheet.max_row + 1):
        cluster, seg = sheet.value(f"B{r}"), sheet.value(f"C{r}")
        if not cluster or not seg:
            continue
        cluster = str(cluster).strip()
        for alt in parse_tw_segment(str(seg), sibs[cluster]):
            dims = tuple(sorted(_cluster_dims(cluster) + list(alt), key=lambda d: d[0]))
            for col, target, excs, label in (("E", pkg, exc_pkg, "1+1"), ("F", satp, exc_satp, "SATP")):
                v = sheet.value(f"{col}{r}")
                cite = XlsxCite(file, sheet.name, f"{col}{r}")
                if isinstance(v, int | float):
                    cell = RateCell(_pct(v), v, cite, label="Max CD2")
                    target.append(
                        RateRule(
                            dims,
                            cell if label == "1+1" else None,
                            cell if label == "SATP" else None,
                            XlsxCite(file, sheet.name, f"B{r}:F{r}"),
                            f"{cluster} · {seg} · {label}",
                        )
                    )
                elif v not in (None, MISSING):
                    excs.append(_code_exception(str(v), cite, dims))
    d3 = XlsxCite(file, sheet.name, "D3")
    return [
        Grid(
            id="godigit/TW 1+1",
            insurer=INSURER,
            file=file,
            title="Go Digit 'TW 1+1 & SATP' (1+1)",
            vehicle_classes=CLASSES,
            policy_types=frozenset({"comprehensive"}),
            business_types=frozenset({"renewal", "rollover"}),
            rules=tuple(pkg),
            mappings=(_rto(wb, file, "C", "1+1 & SATP"),),
            exceptions=tuple(exc_pkg),
            unpublished=(
                Unpublished(
                    "comprehensive",
                    "tp",
                    "Go Digit publishes one CD2 for 1+1 two-wheeler "
                    "policies (applied here to OD); no separate TP rate",
                    d3,
                ),
            ),
            caps=(PKG_CAP,),
        ),
        Grid(
            id="godigit/TW SATP",
            insurer=INSURER,
            file=file,
            title="Go Digit 'TW 1+1 & SATP' (SATP)",
            vehicle_classes=CLASSES,
            policy_types=frozenset({"satp"}),
            rules=tuple(satp),
            mappings=(_rto(wb, file, "C", "1+1 & SATP"),),
            exceptions=tuple(exc_satp),
        ),
    ]


def _new_business(wb: Workbook, file: str, name: str, grid_id: str, term: str, start: int) -> Grid:
    sheet = wb.sheet(name)
    sibs = _siblings(sheet, start, "B", "D")
    makes_by_cluster: dict[str, set[str]] = {}
    from rater.grids.makes import canonical_make

    for r in range(start, sheet.max_row + 1):
        c, m = sheet.value(f"B{r}"), sheet.value(f"C{r}")
        if c and m:
            makes_by_cluster.setdefault(str(c).strip(), set()).update(
                canonical_make(p.strip()) for p in str(m).split("/") if p.strip().lower() != "others"
            )
    rules, excs = [], []
    for r in range(start, sheet.max_row + 1):
        cluster, make, seg = sheet.value(f"B{r}"), sheet.value(f"C{r}"), sheet.value(f"D{r}")
        if not cluster or not seg:
            continue
        cluster = str(cluster).strip()
        v, basis = sheet.value(f"F{r}"), sheet.value(f"G{r}")
        cite = XlsxCite(file, name, f"F{r}")
        for seg_alt in parse_tw_segment(str(seg), sibs[cluster]):
            for make_alt in _make_dims(make, makes_by_cluster.get(cluster, set())):
                dims = tuple(
                    sorted(
                        _cluster_dims(cluster) + list(seg_alt) + make_alt + [("od_term_years", term)],
                        key=lambda d: d[0],
                    )
                )
                if isinstance(v, int | float):
                    rules.append(
                        RateRule(
                            dims,
                            RateCell(_pct(v), v, cite, label=f"Max CD2 ({basis or 'basis not stated'})"),
                            None,
                            XlsxCite(file, name, f"B{r}:G{r}"),
                            f"{cluster} · {make} · {seg}",
                        )
                    )
                elif v not in (None, MISSING):
                    excs.append(_code_exception(str(v), cite, dims))
                note = sheet.value(f"H{r}") if name == "2W Grid 5+5" else None
                if note:
                    k = classify(str(note), "two_wheeler")
                    excs.append(ExceptionRule(k.kind, k.text, XlsxCite(file, name, f"H{r}"), when=dims))
                remark, cut = (
                    (sheet.value(f"J{r}"), sheet.value(f"K{r}")) if name == "2W Grid 5+5" else (None, None)
                )
                if remark and isinstance(cut, int | float):
                    low = str(remark).lower()
                    cond: list[tuple[str, DimValue]] = []
                    if "add on" in low:
                        cond.append(("has_add_ons", "no"))
                    if "cpa" in low:
                        cond.append(("cpa_cover", "no"))
                    excs.append(
                        ExceptionRule(
                            "policy_condition",
                            str(remark),
                            XlsxCite(file, name, f"J{r}"),
                            effect="reduce",
                            percent=abs(_pct(cut)),
                            when=dims + tuple(cond),
                            components=("od",),
                        )
                    )
    return Grid(
        id=grid_id,
        insurer=INSURER,
        file=file,
        title=f"Go Digit '{name}'",
        vehicle_classes=CLASSES,
        policy_types=frozenset({"comprehensive"}),
        business_types=frozenset({"new"}),
        rules=tuple(rules),
        mappings=(_rto(wb, file, "D", "1+5 & 5+5"),),
        exceptions=tuple(excs),
        unpublished=(
            Unpublished(
                "comprehensive",
                "tp",
                f"Go Digit publishes one CD2 for {term}-year OD new "
                "two-wheeler policies (applied here to OD); no separate TP rate",
                XlsxCite(file, name, "F2"),
            ),
        ),
        caps=(PKG_CAP,),
    )


def _saod(wb: Workbook, file: str) -> Grid:
    name = "TW SAOD with Flexi Options"
    sheet = wb.sheet(name)
    sibs = _siblings(sheet, 6, "B", "C")
    rules, excs = [], []
    for r in range(6, sheet.max_row + 1):
        cluster, seg = sheet.value(f"B{r}"), sheet.value(f"C{r}")
        if not cluster or not seg:
            continue
        cluster = str(cluster).strip()
        for alt in parse_tw_segment(str(seg), sibs[cluster]):
            base = _cluster_dims(cluster) + list(alt)
            for col, years in (("H", "1"), ("I", "2"), ("J", "3"), ("K", "4")):
                v = sheet.value(f"{col}{r}")
                if not isinstance(v, int | float):
                    continue
                dims = tuple(sorted(base + [("od_term_years", years)], key=lambda d: d[0]))
                header = str(sheet.value(f"{col}5"))
                rules.append(
                    RateRule(
                        dims,
                        RateCell(_pct(v), v, XlsxCite(file, name, f"{col}{r}"), label=header),
                        None,
                        XlsxCite(file, name, f"B{r}:L{r}"),
                        f"{cluster} · {seg} · {header}",
                    )
                )
            note = sheet.value(f"L{r}")
            if note:
                k = classify(str(note), "two_wheeler")
                excs.append(
                    ExceptionRule(
                        k.kind,
                        k.text,
                        XlsxCite(file, name, f"L{r}"),
                        when=tuple(sorted(base, key=lambda d: d[0])),
                    )
                )
    return Grid(
        id="godigit/TW SAOD",
        insurer=INSURER,
        file=file,
        title=f"Go Digit '{name}'",
        vehicle_classes=CLASSES,
        policy_types=frozenset({"saod"}),
        rules=tuple(rules),
        mappings=(_rto(wb, file, "E", "SAOD"),),
        exceptions=tuple(excs),
        caps=(
            Cap(
                "medium",
                "Go Digit TW SAOD: the 'Max N year CD2' column is used by OD term; the plain "
                "'CD2' column is not",
            ),
        ),
    )


def load(root: Path) -> list[Grid]:
    path = next((root / "raters" / "godigit").rglob("*.xlsx"))
    file = path.relative_to(root).as_posix()
    wb = Workbook(path)
    try:
        return [
            *_one_plus_one(wb, file),
            _new_business(wb, file, "TW 1+5", "godigit/TW 1+5", "1", 3),
            _new_business(wb, file, "2W Grid 5+5", "godigit/2W Grid 5+5", "5", 3),
            _saod(wb, file),
        ]
    finally:
        wb.close()
