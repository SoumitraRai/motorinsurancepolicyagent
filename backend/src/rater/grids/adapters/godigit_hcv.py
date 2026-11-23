"""Go Digit `HCV GRID`: goods vehicles over 12 t, read into the Go Digit CV grids (see `godigit_cv.load`).

The sheet is a stack of blocks. Each block has a body-type row (Non-Dumper/Tipper, Dumper/Tipper, Port
Trailer, Oil Tanker, Gas Tanker; not every block has all five, and the columns move), a Comp/SATP row and a
"Cluster" header row. Each body type has five columns: CD1, Avg CD2 and Max CD2 for Comp, then Avg CD2 and
Max CD2 for SATP. Rows give cluster, segment (GVW band), make (All / TATA) and an age band.

Readings (README assumptions):
- The RTO's cluster comes from the HCV column of `CV RTO Mapping`. RTOs the mapping marks `_LOWCD2_<n>` are
  priced by the Low CD2 rows of `CV Grid (excl. HCV)`, so the rows here exclude them. A mapping value that is
  only a Low CD2 code ("LOWCD2_12TO20_10") names no cluster: `ambiguous`.
- Body types: "Dumper/Tipper" = the body type says dumper or tipper; "Oil Tanker" = says oil tanker; "Gas
  Tanker" = says gas, LPG or CNG tanker; "Port Trailer" = says port trailer. "Non-Dumper/Tipper" is every
  other body. A tanker that is neither oil nor gas, and (where the block has a Port Trailer column) a
  trailer not stated as a port trailer, can't be placed: `ambiguous`.
- A tanker or trailer cell reading "For 0-1 age Non Dumper Tipper grids to be referred" takes the
  Non-Dumper/Tipper rate of the same row (cited there). A TATA cell reading "Above rates to be referred" or
  "same rates ... for all make above" leaves TATA to the block's All-makes rows; otherwise a TATA row
  overrides the All-makes rows at its own ages.
- Cells split by label: With/Without Addon (whether the schedule lists any add-on), Tata/Other Makes,
  West Bengal/North Bengal (mapping clusters), 40-44T/44T+, Age 6-10/Age 10+ (both include age 10, so a
  10-year-old vehicle gets two rates: `ambiguous`). A West Bengal cell that doesn't name North Bengal says
  nothing about North Bengal RTOs: `ambiguous` for them.
- "x%/y%" pairs with a CD1 ladder (OD discount), which the policy doesn't show: `ambiguous`. "D" declines.
  CD1 is the OD discount, not brokerage, so notes about CD1 alone (e.g. "70% CD1") change no rate.
- 'Additional Notes' blocks Volvo and Scania over 12 t. The first block's note instead keeps renewals
  going "at CD2-2.5%": for those clusters a comprehensive renewal is `ambiguous`, new and rollover decline.
- 'Additional Comments' gives Bad GJ-1/Bad GJ-2 12-20 t 6+ year rates that differ from the rows: both are
  loaded, so the resolver reports the contradiction (`ambiguous`).
- "For NL RTO vehicles" side tables give other rates for NL-registered vehicles "with address proof",
  which the policy can't show: NL RTOs are `ambiguous`.
"""

import math
import re
from dataclasses import dataclass, field

from openpyxl.utils import column_index_from_string, get_column_letter

from rater.citations import XlsxCite
from rater.grids.adapters.godigit_4w import _pct
from rater.grids.adapters.godigit_cv import _age_band, _clean, _cluster_keys
from rater.grids.bands import Band
from rater.grids.cvsegments import parse_cv_segment
from rater.grids.model import ContainsAny, DimValue, ExceptionRule, NotContainsAny, NotIn, RateCell, RateRule
from rater.grids.xlsx import MISSING, Sheet, Workbook

SHEET = "HCV GRID"
MAP = "CV RTO Mapping"
INF = math.inf
HCV: tuple[tuple[str, DimValue], ...] = (
    ("gvw_t", Band(12, INF, False, True, "t", "GVW over 12 t")),
    ("vehicle_class", "gcv"),
)
OIL = frozenset({"OIL TANKER"})
GAS = frozenset({"GAS TANKER", "LPG TANKER", "CNG TANKER"})
BLOCKED = frozenset({"VOLVO", "SCANIA"})

Dims = list[tuple[str, DimValue]]

_REFER_YOUNG = re.compile(r"for\s*0-1\s*age\s*non\s*dumper\s*tipper\s*grids?\s*to\s*be\s*referred", re.I)
_REFER_ALL = re.compile(r"above\s*rates\s*to\s*be\s*referred|same\s*rates.*all\s*make\s*above", re.I)
_VALUE = r"-?\d+(?:\.\d+)?\s*%(?:\s*/\s*\d+(?:\.\d+)?\s*%)*|D"


@dataclass(frozen=True)
class Body:
    body: str
    col: str  # the CD1 column; Max CD2 is col+2 (Comp) and col+4 (SATP)

    def column(self, offset: int) -> str:
        return get_column_letter(column_index_from_string(self.col) + offset)

    def dims(self, trailer_column: bool) -> Dims:
        if self.body == "Dumper/Tipper":
            return [("body_type", ContainsAny(frozenset({"DUMPER", "TIPPER"})))]
        if self.body == "Oil Tanker":
            return [("body_type", ContainsAny(OIL))]
        if self.body == "Gas Tanker":
            return [("body_type", ContainsAny(GAS))]
        if self.body == "Port Trailer":
            return [("body_type", ContainsAny(frozenset({"PORT TRAILER"})))]
        others = {"DUMPER", "TIPPER", "TANKER"} | ({"TRAILER"} if trailer_column else set())
        return [("body_type", NotContainsAny(frozenset(others)))]


@dataclass
class Block:
    header: int  # the "Cluster" row
    bodies: tuple[Body, ...]
    rows: tuple[int, ...] = ()
    notes: tuple[int, ...] = ()  # "Note: ..." rows after the block

    @property
    def trailer_column(self) -> bool:
        return any(b.body == "Port Trailer" for b in self.bodies)


_BODIES = ("Non-Dumper/Tipper", "Dumper/Tipper", "Port Trailer", "Oil Tanker", "Gas Tanker")


def blocks(sheet: Sheet) -> list[Block]:
    headers = [
        r
        for r in range(1, sheet.max_row + 1)
        if _clean(sheet.value(f"A{r}") or "") == "Cluster" and _clean(sheet.value(f"F{r}") or "") == "CD1"
    ]
    out: list[Block] = []
    for i, h in enumerate(headers):
        bodies = []
        for c in range(6, sheet.max_column + 1):
            col = get_column_letter(c)
            label = _clean(sheet.value(f"{col}{h - 2}") or "")
            if label not in _BODIES:
                continue
            body = Body(label, col)
            heads = (sheet.value(f"{col}{h - 1}"), sheet.value(f"{body.column(3)}{h - 1}"))
            maxes = (sheet.value(f"{body.column(2)}{h}"), sheet.value(f"{body.column(4)}{h}"))
            if heads != ("Comp", "SATP") or maxes != ("Max CD2", "Max CD2"):
                raise ValueError(f"Go Digit '{SHEET}' block at row {h}: unexpected columns for {label}")
            bodies.append(body)
        end = headers[i + 1] - 2 if i + 1 < len(headers) else sheet.max_row + 1
        rows, notes = [], []
        for r in range(h + 1, end):
            a, b = _clean(sheet.value(f"A{r}") or ""), _clean(sheet.value(f"B{r}") or "")
            if a and re.match(r"gcv\s*4", b, re.I):
                rows.append(r)
            elif a.lower().startswith("note"):
                notes.append(r)
            elif a.lower().startswith("additional"):
                break
        out.append(Block(h, tuple(bodies), tuple(rows), tuple(notes)))
    return out


# ------------------------------------------------------------------------------------------------ cells


@dataclass(frozen=True)
class Part:
    dims: tuple[tuple[str, DimValue], ...] = ()
    percent: float | None = None
    code: str | None = None  # "D"
    reason: str | None = None  # why the part gives no single rate


def _label_dims(label: str) -> Dims | None:
    low = label.lower().strip()
    if low == "with addon":
        return [("has_add_ons", "yes")]
    if low == "without addon":
        return [("has_add_ons", "no")]
    if low == "tata":
        return [("make", "TATA")]
    if low in ("other makes", "non tata"):
        return [("make", NotIn(frozenset({"TATA"})))]
    if low in ("west bengal", "north bengal"):
        return [("cluster", frozenset({low.upper()}))]
    if low.startswith("age"):
        band = _age_band(low.removeprefix("age").strip())
        return [("age", band)] if band else None
    seg = parse_cv_segment(f"GCV4 {label}")
    if not isinstance(seg, str) and not seg.undefined:
        return [(d, w) for d, w in seg.dims if d == "gvw_t"]
    return None


def _value(text: str) -> Part:
    t = _clean(text)
    if t.upper() == "D":
        return Part(code="D")
    if "/" in t:
        return Part(reason=f"Max CD2 '{t}' gives several rates, depending on the CD1 (OD discount) chosen")
    pct = float(t.rstrip("% "))
    if pct < 0:
        return Part(reason=f"Max CD2 '{t}' is not a payout")
    return Part(percent=pct)


def _cell(v: object) -> list[Part] | None:
    if v is None or v is MISSING:
        return None
    if isinstance(v, int | float):
        return [Part(percent=_pct(v))]
    s = str(v).strip()
    if re.fullmatch(_VALUE, s):
        return [_value(s)]
    parts = []
    for line in [x for x in s.split("\n") if x.strip()]:
        m = re.fullmatch(rf"\s*(?P<label>[^:]+?)\s*:?\s*(?P<val>{_VALUE})\s*", line)
        dims = _label_dims(m["label"]) if m else None
        if not m or dims is None:
            return [Part(reason=f"Max CD2 '{_clean(s)}' could not be read as one rate per policy")]
        part = _value(m["val"])
        parts.append(Part(tuple(dims), part.percent, part.code, part.reason))
    return parts


# ------------------------------------------------------------------------------------------------- rows


@dataclass
class Row:
    r: int
    cluster: str
    keys: frozenset[str]
    segment: str
    make: str  # "All" | "TATA"
    age: Band
    dims: Dims = field(default_factory=list)

    def when(self, *extra: tuple[str, DimValue]) -> tuple[tuple[str, DimValue], ...]:
        cluster = [w for d, w in extra if d == "cluster"]
        dims = [*HCV, ("cluster", cluster[0] if cluster else self.keys), *self.dims]
        dims += [(d, w) for d, w in extra if d != "cluster"]
        return tuple(sorted(dict.fromkeys(dims), key=lambda d: d[0]))


def _row(sheet: Sheet, r: int, lows: dict[str, set[str]]) -> Row:
    cluster = _clean(sheet.value(f"A{r}"))
    segment = _clean(sheet.value(f"B{r}"))
    seg = parse_cv_segment(segment)
    if isinstance(seg, str):
        raise ValueError(f"Go Digit '{SHEET}' row {r}: {seg}")
    lo, hi = int(sheet.value(f"D{r}")), int(sheet.value(f"E{r}"))
    age = (
        Band(lo, INF, True, True, "years", f"{lo}+")
        if hi >= 99
        else Band(lo, hi, True, True, "years", f"{lo}-{hi}")
    )
    make = _clean(sheet.value(f"C{r}") or "All")
    keys = _cluster_keys(cluster)
    dims: Dims = [(d, w) for d, w in seg.dims if d != "vehicle_class"]
    if make.upper() == "TATA":
        dims.append(("make", "TATA"))
    if any(lows.get(k) for k in keys):
        dims.append(("low_cd2", "no"))
    return Row(r, cluster, keys, segment, make, age, dims)


def _cd1_text(sheet: Sheet, body: Body, r: int) -> str:
    coord = f"{body.col}{r}"
    rng = sheet.merged(coord)
    v = sheet.value(rng.split(":")[0] if rng else coord)
    return v if isinstance(v, str) else ""


def _referral(sheet: Sheet, body: Body, r: int) -> str | None:
    """'young' (take the Non-Dumper/Tipper rate), 'all' (take the All-makes rows) or None."""
    text = _cd1_text(sheet, body, r)
    if _REFER_YOUNG.search(text):
        return "young"
    if _REFER_ALL.search(text):
        return "all"
    return None


def _split_age(age: Band, taken: list[Band]) -> list[tuple[Band, bool]]:
    """`age` cut into whole-year runs inside (True) and outside (False) the `taken` bands."""
    if not taken:
        return [(age, False)]
    runs: list[list] = []  # [first year, last year, inside]
    for year in range(int(age.lo), int(min(age.hi, 100)) + 1):
        inside = any(b.contains(year) for b in taken)
        if runs and runs[-1][2] == inside:
            runs[-1][1] = year
        else:
            runs.append([year, year, inside])
    if math.isinf(age.hi):
        runs[-1][1] = INF
    out = []
    for lo, hi, inside in runs:
        label = f"{lo}+" if math.isinf(hi) else (f"{lo}-{hi}" if lo != hi else str(lo))
        out.append((Band(lo, hi, True, True, "years", label), inside))
    return out


# ------------------------------------------------------------------------------------------------ rules


@dataclass
class Out:
    rules: list[RateRule] = field(default_factory=list)
    exceptions: list[ExceptionRule] = field(default_factory=list)


def _component(
    sheet: Sheet, file: str, block: Block, rows: dict[int, Row], offset: int, component: str
) -> Out:
    out = Out()
    first = block.bodies[0]
    for body in block.bodies:
        # TATA rows with their own cells, by (cluster, segment): All-makes rows exclude TATA at those ages.
        tata: dict[tuple[str, str], list[Band]] = {}
        for r in block.rows:
            row = rows[r]
            if row.make.upper() == "TATA" and _referral(sheet, body, r) != "all":
                tata.setdefault((row.cluster.upper(), row.segment.lower()), []).append(row.age)
        for r in block.rows:
            row = rows[r]
            how = _referral(sheet, body, r)
            if how == "all":
                continue
            src = first if how == "young" else body
            col = src.column(offset)
            v = sheet.value(f"{col}{r}")
            parts = _cell(v)
            if parts is None:
                continue
            cite = XlsxCite(file, SHEET, f"{col}{r}")
            bdims = body.dims(block.trailer_column)
            pieces = [(row.age, False)]
            if row.make.upper() != "TATA":
                pieces = _split_age(row.age, tata.get((row.cluster.upper(), row.segment.lower()), []))
            for age, excl in pieces:
                extra: Dims = [*bdims, ("age", age)]
                if excl:
                    extra.append(("make", NotIn(frozenset({"TATA"}))))
                _emit(out, row, parts, extra, v, cite, component, body, how)
            if "WEST BENGAL" in row.keys and not any(d == "cluster" for p in parts for d, _ in p.dims):
                out.exceptions.append(
                    ExceptionRule(
                        "unclassified",
                        f"'{SHEET}' row {r} gives a West Bengal rate here without naming North Bengal, "
                        "though other cells of the row split the two",
                        cite,
                        when=row.when(*bdims, ("age", row.age), ("cluster", frozenset({"NORTH BENGAL"}))),
                        components=(component,),
                    )
                )
    return out


def _emit(
    out: Out,
    row: Row,
    parts: list[Part],
    extra: Dims,
    raw: object,
    cite: XlsxCite,
    component: str,
    body: Body,
    how: str | None,
) -> None:
    for part in parts:
        pdims = list(part.dims)
        if any(d == "age" for d, _ in pdims):
            extra = [(d, w) for d, w in extra if d != "age"]
        if any(d == "make" for d, _ in pdims):
            extra = [(d, w) for d, w in extra if d != "make"]
        when = row.when(*extra, *pdims)
        if part.reason:
            out.exceptions.append(
                ExceptionRule(
                    "unclassified", f"{part.reason} (row {row.r})", cite, when=when, components=(component,)
                )
            )
            continue
        if part.code:
            out.exceptions.append(
                ExceptionRule(
                    "policy_condition",
                    f"The grid gives '{part.code}' instead of a rate",
                    cite,
                    effect="decline",
                    when=when,
                    components=(component,),
                )
            )
            continue
        assert part.percent is not None
        label = f"Max CD2 ({'SATP' if component == 'tp' else 'COMP'})"
        cell = RateCell(part.percent, raw, cite, label=label)
        name = f"{row.cluster} · {row.segment} · {row.make} · age {dict(when)['age'].label} · {body.body}"  # type: ignore[union-attr]
        if how == "young":
            name += " (0-1 age: Non-Dumper/Tipper rate)"
        out.rules.append(
            RateRule(
                when,
                cell if component == "od" else None,
                cell if component == "tp" else None,
                XlsxCite(cite.file, SHEET, f"A{row.r}:{cite.range}"),
                name,
            )
        )


def _block_exceptions(file: str, block: Block, rows: dict[int, Row]) -> list[ExceptionRule]:
    keys = frozenset().union(*(rows[r].keys for r in block.rows)) if block.rows else frozenset()
    if not keys:
        return []
    base = (*HCV, ("cluster", keys))
    cite = XlsxCite(file, SHEET, f"{block.bodies[0].col}{block.header - 2}")
    out = [
        ExceptionRule(
            "unclassified",
            "the body type is a tanker but not stated as an oil or gas tanker; the grid prices those apart",
            cite,
            when=(
                *base,
                ("body_type", ContainsAny(frozenset({"TANKER"}))),
                ("body_type", NotContainsAny(OIL | GAS)),
            ),
        )
    ]
    if block.trailer_column:
        out.append(
            ExceptionRule(
                "unclassified",
                "the body type is a trailer but not stated as a port trailer; the grid prices port "
                "trailers apart",
                cite,
                when=(
                    *base,
                    ("body_type", ContainsAny(frozenset({"TRAILER"}))),
                    ("body_type", NotContainsAny(frozenset({"PORT TRAILER"}))),
                ),
            )
        )
    return out


def _find(sheet: Sheet, pattern: str) -> list[str]:
    return [c for c, v in sheet.cells() if isinstance(v, str) and re.search(pattern, v, re.I)]


def _blocked(
    sheet: Sheet, file: str, found: list[Block], rows: dict[int, Row]
) -> tuple[list[ExceptionRule], list[ExceptionRule]]:
    """Volvo / Scania: (comprehensive, SATP) exceptions."""
    blocked = next(
        r
        for r in range(1, sheet.max_row + 1)
        if re.search(r"volvo\s*&\s*scania", str(sheet.value(f"B{r}") or ""), re.I)
    )
    make_text, segment, note = (_clean(sheet.value(f"{c}{blocked}")) for c in "BCE")
    text = f"{make_text} ({segment}): {note}"
    cite = XlsxCite(file, SHEET, f"A{blocked}:E{blocked}")
    make = ("make", BLOCKED)
    renew: frozenset[str] = frozenset()
    renew_note = None
    for block in found:
        for n in block.notes:
            note = _clean(sheet.value(f"A{n}"))
            if re.search(r"volvo.*rene", note, re.I):
                renew |= frozenset().union(*(rows[r].keys for r in block.rows))
                renew_note = (n, note)
    satp = [ExceptionRule("policy_condition", text, cite, effect="decline", when=(*HCV, make))]
    if not renew_note:
        return satp, satp
    n, note = renew_note
    ncite = XlsxCite(file, SHEET, f"A{n}")
    comp = [
        ExceptionRule(
            "policy_condition", text, cite, effect="decline", when=(*HCV, make, ("cluster", NotIn(renew)))
        ),
        ExceptionRule(
            "policy_condition",
            note,
            ncite,
            effect="decline",
            when=(*HCV, make, ("cluster", renew), ("business_type", frozenset({"new", "rollover"}))),
        ),
        ExceptionRule(
            "unclassified",
            f"'{SHEET}' note (row {n}) continues Volvo/Scania renewals 'at CD2-2.5%' (Rene-wals), while "
            f"'Additional Notes' (row {blocked}) blocks them",
            ncite,
            when=(*HCV, make, ("cluster", renew), ("business_type", "renewal")),
        ),
    ]
    return comp, satp


def _comments(sheet: Sheet, file: str) -> tuple[list[RateRule], list[RateRule]]:
    """'Additional Comments' rows as rate rules: (comprehensive, SATP)."""
    start = next(
        (
            r
            for r in range(1, sheet.max_row + 1)
            if _clean(sheet.value(f"A{r}") or "") == "Additional Comments:"
        ),
        None,
    )
    comp: list[RateRule] = []
    satp: list[RateRule] = []
    if start is None:
        return comp, satp
    bodies = {"oil tanker": Body("Oil Tanker", "A"), "gas tanker": Body("Gas Tanker", "A")}
    for r in range(start + 2, sheet.max_row + 1):
        label, seg_text, product, text = (sheet.value(f"{c}{r}") for c in "ABCD")
        if not label or not isinstance(text, str):
            continue
        cluster = _clean(label).split(" - ")[-1]
        seg = parse_cv_segment(_clean(seg_text))
        if isinstance(seg, str):
            raise ValueError(f"Go Digit '{SHEET}' row {r}: {seg}")
        p = _clean(product).lower()
        body = next((b for k, b in bodies.items() if k in p), Body("Non-Dumper/Tipper", "A"))
        dims = (
            *HCV,
            ("cluster", _cluster_keys(cluster)),
            *[(d, w) for d, w in seg.dims if d != "vehicle_class"],
            *body.dims(False),
            ("make", NotIn(BLOCKED)),
        )
        when = tuple(sorted(dict.fromkeys(dims), key=lambda d: d[0]))
        cite = XlsxCite(file, SHEET, f"D{r}")
        row_cite = XlsxCite(file, SHEET, f"A{r}:D{r}")
        name = f"Additional Comments · {cluster} · {_clean(seg_text)} · {_clean(product)}"
        for out, key, component in ((comp, "CD2", "od"), (satp, "SATP", "tp")):
            m = re.search(rf"\b{key}\s*-\s*(\d+(?:\.\d+)?)\s*%", text)
            if not m:
                continue
            cell = RateCell(float(m[1]), text, cite, label=f"{key} (Additional Comments)")
            out.append(
                RateRule(
                    when,
                    cell if component == "od" else None,
                    cell if component == "tp" else None,
                    row_cite,
                    name,
                )
            )
    return comp, satp


def _mapping_exceptions(wb: Workbook, file: str, sheet: Sheet) -> list[ExceptionRule]:
    mapping = wb.sheet(MAP)
    out: list[ExceptionRule] = []
    codes: dict[str, str] = {}
    nl: set[str] = set()
    for r in range(3, mapping.max_row + 1):
        code, v = mapping.value(f"A{r}"), mapping.value(f"G{r}")
        if not code:
            continue
        if str(code).upper().startswith("NL"):
            nl.add(_clean(code))
        text = _clean(v or "").upper()
        if re.search(r"(^|_)LOWCD2_\d+TO\d+", text):
            codes.setdefault(text, f"A{r}:G{r}")
    for text, rng in sorted(codes.items()):
        out.append(
            ExceptionRule(
                "unclassified",
                f"'{MAP}' gives '{text}' for this RTO's HCV column: a Low CD2 code without a cluster, which "
                f"neither '{SHEET}' nor 'CV Grid (excl. HCV)' has rows for",
                XlsxCite(file, MAP, rng),
                when=(*HCV, ("cluster", frozenset({text}))),
            )
        )
    side = _find(sheet, r"for\s*nl\s*rto\s*vehicles")
    if nl and side:
        out.append(
            ExceptionRule(
                "unclassified",
                f"'{SHEET}' gives separate rates 'For NL RTO vehicles' ({', '.join(side)}) that apply only "
                "with address proof, which the policy does not show",
                XlsxCite(file, SHEET, side[0]),
                when=(*HCV, ("rto", frozenset(nl))),
            )
        )
    return out


def load_into(wb: Workbook, file: str, lows: dict[str, set[str]]) -> tuple[Out, Out]:
    """(comprehensive, SATP) rules and exceptions from `HCV GRID`."""
    sheet = wb.sheet(SHEET)
    found = blocks(sheet)
    rows = {r: _row(sheet, r, lows) for block in found for r in block.rows}
    comp, satp = Out(), Out()
    for block in found:
        for out, offset, component in ((comp, 2, "od"), (satp, 4, "tp")):
            part = _component(sheet, file, block, rows, offset, component)
            out.rules += part.rules
            out.exceptions += part.exceptions
            out.exceptions += _block_exceptions(file, block, rows)
    comp_blocked, satp_blocked = _blocked(sheet, file, found, rows)
    comp.exceptions += comp_blocked
    satp.exceptions += satp_blocked
    comp_comments, satp_comments = _comments(sheet, file)
    comp.rules += comp_comments
    satp.rules += satp_comments
    shared = _mapping_exceptions(wb, file, sheet)
    comp.exceptions += shared
    satp.exceptions += shared
    return comp, satp
