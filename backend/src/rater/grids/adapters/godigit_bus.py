"""Go Digit `School & Staff Bus ` with the `School & Staff Bus RTO` RTO → cluster map.

Two tables. School Bus: B state, C RTO cluster, D seating capacity, then Max CD2 by who runs the bus:
E "In the name of School", F "On Contract (Transporter)", G "On Contract (Individual)". Staff Bus: C RTO
cluster, then D "Corporate [Self-Usage]", E "Contract Carriage Transporter", F "Contract Carriage
Individual" as "CD1 95% / CD2 40%" text; G seating capacity (">10", merged over the table).

Readings (README assumptions):
- One grid for both bus classes, comprehensive only: the sheet gives one Max CD2 for the package (reported
  as OD, TP unpublished, confidence capped). No SATP rates, so SATP buses are `unsupported`.
- Who runs the bus (`bus_operator`: school / corporate / transporter / individual) is not a policy fact, so
  a rate that differs between those columns is `ambiguous`. Where every column gives the same answer (e.g.
  all "D"), the operator isn't needed.
- A cell merged over two columns gives both columns' answer. In the staff table, the CD2 of
  "CD1 95% / CD2 40%" is the payout; CD1 (the OD discount) is fixed, so it is not a ladder.
- Notes: a school bus under 8 seats gets no school-bus rate (the taxi grid is not applied to another
  vehicle class): `unsupported`. Staff buses up to 10 seats get "CD1_85% & CD2_20% in all open cohorts",
  which the sheet doesn't define: `ambiguous`. The staff grid is for non-electric buses. Short-term
  reductions depend on the policy term, which is not read: `ambiguous` if they could apply. Document and
  system notes are process notes (shown in the trace).
- Both tables apply from 1 March 2026 ("Applicable from 1st of Mar, 2026", "Effective 1 Mar'26").
"""

import math
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from rater.citations import XlsxCite
from rater.grids.adapters.godigit_4w import _pct
from rater.grids.bands import Band
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
from rater.grids.xlsx import MISSING, Sheet, Workbook
from rater.resolve.confidence import Cap

INSURER = "Go Digit"
SHEET = "School & Staff Bus "
MAP = "School & Staff Bus RTO"
INF = math.inf
PKG_CAP = Cap("medium", "Go Digit bus Max CD2 is one rate for the package; reported as OD, TP unpublished")

Dims = list[tuple[str, DimValue]]


def _clean(text: object) -> str:
    return " ".join(str(text).split())


@dataclass(frozen=True)
class Table:
    vehicle_class: str
    header: str  # text in column B that starts the table
    seats_col: str
    operators: tuple[tuple[str, str], ...]  # (column, bus_operator)
    map_cols: tuple[str, str]  # RTO code, cluster


SCHOOL = Table(
    "school_bus", "School Bus", "D", (("E", "school"), ("F", "transporter"), ("G", "individual")), ("B", "E")
)
STAFF = Table(
    "staff_bus", "Staff Bus", "G", (("D", "corporate"), ("E", "transporter"), ("F", "individual")), ("I", "L")
)


def _anchor(sheet: Sheet, coord: str) -> str:
    rng = sheet.merged(coord)
    return rng.split(":")[0] if rng else coord


def _seats(text: object) -> Band | None:
    t = _clean(text).lower()
    if t in ("", "all"):
        return None
    if m := re.fullmatch(r"(\d+)\s*&\s*above", t):
        return Band(int(m[1]), INF, True, True, "seats", f"{m[1]} & above")
    if m := re.fullmatch(r">\s*(\d+)", t):
        return Band(int(m[1]), INF, False, True, "seats", f">{m[1]}")
    if m := re.fullmatch(r"(\d+)\s*-\s*(\d+)", t):
        return Band(int(m[1]), int(m[2]), True, True, "seats", f"{m[1]}-{m[2]}")
    raise ValueError(f"Go Digit '{SHEET}': seating capacity '{t}' could not be read")


def _answer(v: object) -> float | str | None:
    """A rate (percent), "D" for a decline, or None for an empty cell."""
    if v is None or v is MISSING:
        return None
    if isinstance(v, int | float):
        return _pct(v)
    t = _clean(v)
    if t.upper() == "D" or t.lower() == "decline":
        return "D"
    if m := re.fullmatch(r"cd1\s*\d+(?:\.\d+)?\s*%\s*/\s*cd2\s*(\d+(?:\.\d+)?)\s*%", t, re.I):
        return float(m[1])
    raise ValueError(f"Go Digit '{SHEET}': rate cell '{t}' could not be read")


def _start(sheet: Sheet, header: str) -> int:
    """The row whose column B starts with `header` (a table's title)."""
    return next(
        r for r in range(1, sheet.max_row + 1) if _clean(sheet.value(f"B{r}") or "").startswith(header)
    )


def _rows(sheet: Sheet, table: Table) -> range:
    start = _start(sheet, table.header)
    first = start + 3  # title, header, sub-header
    last = first
    for r in range(first, sheet.max_row + 1):
        if sheet.value(_anchor(sheet, f"C{r}")) and any(
            sheet.value(f"{c}{r}") is not None for c, _ in table.operators
        ):
            last = r
        elif r > first:
            break
    return range(first, last + 1)


def _table(sheet: Sheet, file: str, table: Table) -> tuple[list[RateRule], list[ExceptionRule]]:
    rules: list[RateRule] = []
    excs: list[ExceptionRule] = []
    for r in _rows(sheet, table):
        cluster = _clean(sheet.value(_anchor(sheet, f"C{r}")))
        seats = _seats(sheet.value(_anchor(sheet, f"{table.seats_col}{r}")))
        cells = [(col, op, _anchor(sheet, f"{col}{r}")) for col, op in table.operators]
        answers = {coord: _answer(sheet.value(coord)) for _, _, coord in cells}
        same = len(set(answers.values())) == 1
        base: Dims = [("vehicle_class", table.vehicle_class), ("cluster", frozenset({cluster.upper()}))]
        if seats is not None:
            base.append(("seating_capacity", seats))
        if table is STAFF:
            base.append(("fuel", NotIn(frozenset({"electric"}))))
        done: set[str] = set()
        for _col, op, coord in cells:
            answer = answers[coord]
            if answer is None:
                continue
            dims = base if same else [*base, ("bus_operator", op)]
            when = tuple(sorted(dims, key=lambda d: d[0]))
            cite = XlsxCite(file, SHEET, coord)
            if answer == "D":
                if coord not in done or not same:
                    excs.append(
                        ExceptionRule(
                            "policy_condition",
                            "The grid gives 'D' instead of a rate",
                            cite,
                            "decline",
                            when=when,
                        )
                    )
                done.add(coord)
                continue
            assert isinstance(answer, float)
            raw = sheet.value(coord)
            rules.append(
                RateRule(
                    when,
                    RateCell(answer, raw, cite, label=f"Max CD2 ({op})"),
                    None,
                    XlsxCite(file, SHEET, f"B{r}:{table.operators[-1][0]}{r}"),
                    f"{table.header} · {cluster}" + (f" · {seats.label} seats" if seats else "") + f" · {op}",
                )
            )
    return rules, excs


def _notes(sheet: Sheet, file: str) -> list[ExceptionRule]:
    staff_start = _start(sheet, STAFF.header)
    out: list[ExceptionRule] = []
    for coord, v in sheet.cells():
        if not isinstance(v, str) or not coord.startswith(("B", "F")):
            continue
        r = int(re.sub(r"^[A-Z]+", "", coord))
        text = _clean(v)
        low = text.lower()
        if low == "note:":
            continue
        vc = STAFF.vehicle_class if r > staff_start else SCHOOL.vehicle_class
        cite = XlsxCite(file, SHEET, coord)
        base: tuple[tuple[str, DimValue], ...] = (("vehicle_class", vc),)
        if re.search(r"short[\s-]*term", low):
            # The policy term is not read, so whether this applies stays open (`short_term` is never known).
            out.append(ExceptionRule("policy_condition", text, cite, when=(*base, ("short_term", "yes"))))
        elif re.search(r"less\s*than\s*8\s*seater", low):
            seats = Band(0, 8, True, False, "seats", "under 8")
            out.append(
                ExceptionRule(
                    "policy_condition", text, cite, "decline", when=(*base, ("seating_capacity", seats))
                )
            )
        elif re.search(r"up\s*to\s*10\s*-?\s*seater", low):
            seats = Band(0, 10, True, True, "seats", "up to 10")
            out.append(ExceptionRule("unclassified", text, cite, when=(*base, ("seating_capacity", seats))))
        elif re.search(r"non[\s-]*electric", low):
            out.append(
                ExceptionRule("policy_condition", text, cite, "decline", when=(*base, ("fuel", "electric")))
            )
        elif re.match(r"\d\.\s|note\b|\*|for new vehicles|system guidelines|buses which are blocked", low):
            out.append(ExceptionRule("process", text, cite, when=base))
    return out


_MONTHS = {
    m: i
    for i, m in enumerate(
        ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"), 1
    )
}


def _from_date(text: str) -> date:
    m = re.search(r"(\d{1,2})(?:st|nd|rd|th)?\s*(?:of\s*)?([a-z]{3})[a-z]*,?\s*(\d{4})", text, re.I)
    if not m or m[2].lower() not in _MONTHS:
        raise ValueError(f"Go Digit '{SHEET}': start date '{text}' could not be read")
    return date(int(m[3]), _MONTHS[m[2].lower()], int(m[1]))


def _mapping(wb: Workbook, file: str, table: Table) -> MappingTable:
    sheet = wb.sheet(MAP)
    code_col, cluster_col = table.map_cols
    rows = []
    for r in range(3, sheet.max_row + 1):
        code, value = sheet.value(f"{code_col}{r}"), sheet.value(f"{cluster_col}{r}")
        if not code or value is None or value is MISSING:
            continue
        cite = XlsxCite(file, MAP, f"{code_col}{r}:{cluster_col}{r}")
        rows.append(MappingRow(_clean(code), _clean(value).upper(), cite, raw=code))
    name = f"Go Digit {table.header.lower()} RTO → cluster ({MAP}, column {cluster_col})"
    return MappingTable(name, "rto", "cluster", tuple(rows), when=(("vehicle_class", table.vehicle_class),))


def load(root: Path) -> list[Grid]:
    path = next((root / "raters" / "godigit").rglob("*.xlsx"))
    file = path.relative_to(root).as_posix()
    wb = Workbook(path)
    try:
        sheet = wb.sheet(SHEET)
        rules: list[RateRule] = []
        excs: list[ExceptionRule] = []
        for table in (SCHOOL, STAFF):
            t_rules, t_excs = _table(sheet, file, table)
            rules += t_rules
            excs += t_excs
        excs += _notes(sheet, file)
        mappings = (_mapping(wb, file, SCHOOL), _mapping(wb, file, STAFF))
        date_text = _clean(sheet.value("B2"))
    finally:
        wb.close()
    return [
        Grid(
            id="godigit/Bus Comp",
            insurer=INSURER,
            file=file,
            title=f"Go Digit '{SHEET.strip()}' (comprehensive)",
            vehicle_classes=frozenset({SCHOOL.vehicle_class, STAFF.vehicle_class}),
            policy_types=frozenset({"comprehensive"}),
            rules=tuple(rules),
            mappings=mappings,
            exceptions=tuple(excs),
            unpublished=(
                Unpublished(
                    "comprehensive",
                    "tp",
                    "Go Digit publishes one CD2 for comprehensive bus policies (applied here to OD); "
                    "no separate TP rate",
                    XlsxCite(file, SHEET, "E5"),
                ),
            ),
            effective_from=_from_date(date_text),
            date_text=date_text,
            date_cite=XlsxCite(file, SHEET, "B2"),
            caps=(PKG_CAP,),
        )
    ]
