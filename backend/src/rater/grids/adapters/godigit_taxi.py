"""Go Digit `TAXI Segments and Location wise`, read into the Go Digit CV grids (see `godigit_cv.load`).

Columns: B cluster, C segment (seats, fuel, cc, sometimes age), D make, E with/without add-on cover, F CD1
(not brokerage), G Max CD2 for comprehensive, H Max CD2 for SATP, I note (often merged over rows).

Readings (README assumptions):
- The RTO's cluster comes from `CV RTO Mapping` (up to 5 seats, or 6+ seats, by seating capacity).
- "With Add on cover" = the schedule lists an add-on cover. "< 1000 cc" and "> 1000 cc" leave exactly
  1000 cc between the rows: `ambiguous`. "non-diesel" = petrol/CNG/LPG (Electric has its own rows).
- Make scopes: "Other"/"All" beside named makes cover the makes their siblings (same cluster, segment and
  add-on) don't name; "Other than X" excludes X. Ages written into the make column ("Hyundai Age 0",
  "Maruti (all age) & Hyundai age 1+") split the row.
- "Kaali peeli" (black-and-yellow taxi) rows price a kind of taxi the policy can't be shown to be: a
  policy they could cover is `ambiguous`.
- WagonR: where a cluster's notes say WagonR takes the "> 1000 cc" grid (or a segment says "WagonR
  Included"), a WagonR is priced by the "> 1000 cc" rows whatever its cc.
- "(including Ertiga, Maruti XI6, ECO, Invicto)": those models take the row whatever their seats ("XI6" is
  read as the XL6). Where another row also covers them (Goa's 6-9 seater rows), the grid contradicts itself.
- "Only <RTOs>" notes restrict the rows they span. The monthly-volume bonus note is broker-side: listed,
  not applied (D2).
"""

import math
import re
from dataclasses import dataclass, field

from rater.citations import XlsxCite
from rater.grids.adapters.godigit_4w import _pct
from rater.grids.adapters.godigit_cv import _clean, _cluster_keys, _note
from rater.grids.adapters.godigit_hcv import Out
from rater.grids.bands import Band
from rater.grids.makes import canonical_make
from rater.grids.model import (
    Contains,
    ContainsAny,
    DimValue,
    ExceptionRule,
    NotContainsAny,
    NotIn,
    RateCell,
    RateRule,
)
from rater.grids.textrules import classify
from rater.grids.xlsx import MISSING, Sheet, Workbook

SHEET = "TAXI Segments and Location wise"
INF = math.inf
WAGONR = frozenset({"WAGONR"})

Dims = list[tuple[str, DimValue]]

_SEG = re.compile(
    r"""^taxi\s+(?:upto\s+(?P<upto>\d+)|(?P<lo>\d+)\s*-\s*(?P<hi>\d+))\s*seater\s*
    (?P<fuel>non-diesel|diesel|electric|cng|all)?\s*
    (?P<op><|>)\s*(?P<cc>\d+)\s*cc
    (?:\s*&\s*<=\s*(?P<cc2>\d+)\s*cc)?
    \s*(?P<wagonr>\(\s*wagon\s*r\s+included\s*\))?
    \s*(?:age\s*(?P<age>\d+)\s*(?P<plus>\+)?|(?P<years>\d+)\s*\+\s*years?)?\s*$""",
    re.I | re.X,
)
_FUELS: dict[str, DimValue] = {
    "non-diesel": frozenset({"petrol", "cng", "lpg"}),
    "diesel": "diesel",
    "electric": "electric",
    "cng": "cng",
}


@dataclass(frozen=True)
class TaxiSegment:
    label: str
    dims: tuple[tuple[str, DimValue], ...]
    wagonr_included: bool = False

    @property
    def cc(self) -> Band:
        return next(w for d, w in self.dims if d == "cc")  # type: ignore[return-value]


def parse_taxi_segment(label: str) -> TaxiSegment | str:
    text = " ".join(str(label).split())
    m = _SEG.match(text)
    if not m:
        return f"segment '{text}' is not a recognised taxi segment"
    dims: Dims = [("vehicle_class", "pcv_taxi")]
    if m["upto"]:
        n = int(m["upto"])
        dims.append(("seating_capacity", Band(0, n, True, True, "seats", f"up to {n}")))
    else:
        lo, hi = int(m["lo"]), int(m["hi"])
        dims.append(("seating_capacity", Band(lo, hi, True, True, "seats", f"{lo}-{hi}")))
    fuel = (m["fuel"] or "all").lower()
    if fuel != "all":
        dims.append(("fuel", _FUELS[fuel]))
    cc = int(m["cc"])
    if m["op"] == "<":
        dims.append(("cc", Band(0, cc, True, False, "cc", f"< {cc} cc")))
    else:
        top = int(m["cc2"]) if m["cc2"] else INF
        label_cc = f"> {cc} cc" + (f" & <= {int(top)} cc" if m["cc2"] else "")
        dims.append(("cc", Band(cc, top, False, True, "cc", label_cc)))
    if m["age"]:
        a = int(m["age"])
        dims.append(
            ("age", Band(a, INF if m["plus"] else a, True, True, "years", f"{a}{'+' if m['plus'] else ''}"))
        )
    elif m["years"]:
        a = int(m["years"])
        dims.append(("age", Band(a, INF, True, True, "years", f"{a}+")))
    return TaxiSegment(text, tuple(sorted(dims, key=lambda d: d[0])), bool(m["wagonr"]))


# ------------------------------------------------------------------------------------------------ makes


@dataclass
class MakeScope:
    alternatives: list[Dims] = field(default_factory=lambda: [[]])  # one rule per alternative
    kind: str = "all"  # all | others | makes | except | kaali
    names: frozenset[str] = frozenset()
    models: frozenset[str] = frozenset()  # "(including ...)" models, whatever their seats


def _names(text: str) -> frozenset[str]:
    return frozenset(canonical_make(p.strip()) for p in re.split(r",|&|\band\b", text) if p.strip())


def _age(text: str) -> Band:
    m = re.fullmatch(r"\s*age\s*(\d+)\s*(\+)?\s*", text, re.I)
    if not m:
        raise ValueError(f"Go Digit '{SHEET}': make-column age '{text}' could not be read")
    a = int(m[1])
    return Band(a, INF if m[2] else a, True, True, "years", f"{a}{'+' if m[2] else ''}")


def _make(value: object) -> MakeScope:
    t = _clean(value or "All")
    low = t.lower()
    if low == "all":
        return MakeScope()
    if "kaali" in low:
        m = re.search(r"\((.+)\)", t)
        names = _names(m[1]) if m else frozenset()
        return MakeScope([[("make", names)]] if names else [[]], "kaali", names)
    if low in ("other", "others"):
        return MakeScope(kind="others")
    if m := re.fullmatch(r"others?\s*\(\s*other\s*than\s*(.+?)(?:\s*make)?\s*\)", low) or re.fullmatch(
        r"other\s*than\s*(.+)", low
    ):
        names = _names(m[1])
        return MakeScope([[("make", NotIn(names))]], "except", names)
    if m := re.fullmatch(r"(.+?)\s*\(\s*including\s*(.+)\)", t, re.I):
        names = _names(m[1])
        models = set()
        for p in m[2].split(","):
            words = [w for w in p.split() if canonical_make(w) not in names]
            models.add(" ".join(words).upper())
        if "XI6" in models:
            models.add("XL6")
        return MakeScope([[("make", names)]], "makes", names, frozenset(models))
    if m := re.fullmatch(r"(\w+)\s*-\s*(\w+)", t):
        make = canonical_make(m[1])
        return MakeScope([[("make", make), ("model", Contains(m[2].upper()))]], "makes", frozenset({make}))
    if "(all age)" in low:
        alts: list[Dims] = []
        for piece in t.split("&"):
            names_text, _, age_text = re.sub(r"\(all age\)", "", piece, flags=re.I).partition(" age")
            dims: Dims = [("make", _names(names_text))]
            if age_text.strip():
                dims.append(("age", _age("age" + age_text)))
            alts.append(dims)
        names = frozenset().union(*(w for alt in alts for d, w in alt if d == "make"))  # type: ignore[arg-type]
        return MakeScope(alts, "makes", names)
    if m := re.fullmatch(r"(.+?)\s+(age\s*\d+\s*\+?)", t, re.I):
        names = _names(m[1])
        return MakeScope([[("make", names), ("age", _age(m[2]))]], "makes", names)
    names = _names(t)
    return MakeScope([[("make", names)]], "makes", names)


# ------------------------------------------------------------------------------------------------- rows


@dataclass
class Row:
    r: int
    cluster: str
    keys: frozenset[str]
    seg: TaxiSegment
    make: MakeScope
    addon: str  # yes | no
    note: str  # the I-column text over this row ("" when none)
    note_cell: str  # its anchor cell
    dims: Dims = field(default_factory=list)
    alternatives: list[Dims] = field(default_factory=list)

    @property
    def group(self) -> tuple[str, str, str]:
        label = re.sub(r"\(\s*wagon\s*r\s+included\s*\)", "", self.seg.label, flags=re.I)
        return self.cluster.upper(), " ".join(label.lower().split()), self.addon


def _note_at(sheet: Sheet, r: int) -> tuple[str, str]:
    coord = f"I{r}"
    rng = sheet.merged(coord)
    anchor = rng.split(":")[0] if rng else coord
    v = sheet.value(anchor)
    return (_clean(v), anchor) if isinstance(v, str) else ("", anchor)


def _rows(sheet: Sheet) -> list[Row]:
    rows = []
    for r in range(4, sheet.max_row + 1):
        cluster = sheet.value(f"B{r}")
        if not cluster:
            continue
        seg = parse_taxi_segment(str(sheet.value(f"C{r}")))
        if isinstance(seg, str):
            raise ValueError(f"Go Digit '{SHEET}' row {r}: {seg}")
        addon = _clean(sheet.value(f"E{r}")).lower()
        if addon not in ("with add on cover", "without add on cover"):
            raise ValueError(f"Go Digit '{SHEET}' row {r}: add-on column '{addon}'")
        note, cell = _note_at(sheet, r)
        cluster = _clean(cluster)
        row = Row(
            r, cluster, _cluster_keys(cluster), seg, _make(sheet.value(f"D{r}")),
            "yes" if addon.startswith("with ") else "no", note, cell,
        )  # fmt: skip
        scope = _note(note) if note and not re.search(r"wagon\s*r", note, re.I) else None
        if scope is not None and scope.rtos is not None:
            row.dims.append(("rto", scope.rtos))
        rows.append(row)
    _precedence(rows)
    return rows


def _precedence(rows: list[Row]) -> None:
    groups: dict[tuple[str, str, str], list[Row]] = {}
    for row in rows:
        groups.setdefault(row.group, []).append(row)
    for members in groups.values():
        named = frozenset().union(*(x.make.names for x in members if x.make.kind in ("makes", "kaali")))
        for row in members:
            if row.make.kind in ("all", "others") and named:
                row.dims.append(("make", NotIn(named)))
    wagonr = {
        row.cluster.upper()
        for row in rows
        if row.seg.wagonr_included or re.search(r"wagon\s*r", row.note, re.I)
    }
    for row in rows:
        row.alternatives = [list(a) for a in row.make.alternatives]
        if row.make.models:
            row.alternatives += [
                [*a, ("model", ContainsAny(row.make.models)), ("seating_capacity", None)]  # type: ignore[list-item]
                for a in row.make.alternatives
            ]
        if row.cluster.upper() not in wagonr:
            continue
        cc = row.seg.cc
        if cc.hi == 1000 and not cc.hi_incl:
            row.dims.append(("model", NotContainsAny(WAGONR)))
        elif cc.lo == 1000:
            row.alternatives += [
                [*a, ("model", ContainsAny(WAGONR)), ("cc", None)]  # type: ignore[list-item]
                for a in row.make.alternatives
            ]


def _when(row: Row, alt: Dims) -> tuple[tuple[str, DimValue], ...]:
    """Row dims with an alternative's; an alternative's `(dim, None)` drops that segment dimension."""
    dropped = {d for d, w in alt if w is None}
    dims = [(d, w) for d, w in row.seg.dims if d not in dropped]
    dims += [("cluster", row.keys), ("has_add_ons", row.addon), *row.dims]
    dims += [(d, w) for d, w in alt if w is not None]
    return tuple(sorted(dict.fromkeys(dims), key=lambda d: d[0]))


# ------------------------------------------------------------------------------------------------ rules


def _component(sheet: Sheet, file: str, rows: list[Row], col: str, component: str) -> Out:
    out = Out()
    for row in rows:
        v = sheet.value(f"{col}{row.r}")
        if v is None or v is MISSING:
            continue
        cite = XlsxCite(file, SHEET, f"{col}{row.r}")
        if row.make.kind == "kaali":
            for alt in row.alternatives:
                out.exceptions.append(
                    ExceptionRule(
                        "unclassified",
                        f"'{SHEET}' row {row.r} prices '{_clean(sheet.value(f'D{row.r}'))}' "
                        "(black-and-yellow) taxis apart; the policy does not show whether this taxi is one",
                        cite,
                        when=_when(row, alt),
                    )
                )
            continue
        for alt in row.alternatives:
            when = _when(row, alt)
            if isinstance(v, str) and v.strip().upper() == "D":
                out.exceptions.append(
                    ExceptionRule(
                        "policy_condition",
                        "The grid gives 'D' instead of a rate",
                        cite,
                        effect="decline",
                        when=when,
                    )
                )
                continue
            label = f"Max CD2 ({'SATP' if component == 'tp' else 'COMP'})"
            cell = RateCell(_pct(v), v, cite, label=label)
            name = (
                f"{row.cluster} · {row.seg.label} · {_clean(sheet.value(f'D{row.r}'))} · add-on {row.addon}"
            )
            if any(d == "model" and isinstance(w, ContainsAny) for d, w in alt):
                name += " · " + "/".join(sorted(next(w.texts for d, w in alt if d == "model")))  # type: ignore[union-attr]
            out.rules.append(
                RateRule(
                    when,
                    cell if component == "od" else None,
                    cell if component == "tp" else None,
                    XlsxCite(file, SHEET, f"B{row.r}:I{row.r}"),
                    name,
                )
            )
    return out


def _notes(file: str, rows: list[Row]) -> list[ExceptionRule]:
    out: list[ExceptionRule] = []
    for row in rows:
        if not row.note or re.search(r"wagon\s*r", row.note, re.I):
            continue
        scope = _note(row.note)
        if scope.rtos is not None and not scope.other:
            continue  # applied to the row as an RTO dimension
        k = classify(scope.other or row.note, "pcv_taxi")
        kind = "unclassified" if k.kind in ("policy_condition", "undefined_decline") else k.kind
        for alt in row.alternatives:
            out.append(
                ExceptionRule(kind, k.text, XlsxCite(file, SHEET, row.note_cell), when=_when(row, alt))
            )
    return out


def load_into(wb: Workbook, file: str) -> tuple[Out, Out]:
    """(comprehensive, SATP) rules and exceptions from the taxi sheet."""
    sheet = wb.sheet(SHEET)
    rows = _rows(sheet)
    comp = _component(sheet, file, rows, "G", "od")
    satp = _component(sheet, file, rows, "H", "tp")
    notes = _notes(file, rows)
    comp.exceptions += notes
    satp.exceptions += notes
    return comp, satp
