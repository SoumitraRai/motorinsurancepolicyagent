"""Go Digit commercial vehicles: `CV Grid (excl. HCV)` with the `CV RTO Mapping` RTO → cluster map.

`HCV GRID` (goods vehicles over 12 t) is read by `godigit_hcv` into the same two grids.

Columns: B cluster, C segment (parsed by `cvsegments`), D make / body / age scope, E CD1 (not brokerage),
F Max CD2 for comprehensive, G Max CD2 for SATP, H note.

Readings (README assumptions):
- `CV RTO Mapping` has one cluster column per vehicle type. Goods vehicles use LCV / MCV / HCV by gross
  vehicle weight, with the Motor Vehicles Act weight classes (light up to 7.5 t, medium up to 12 t, heavy
  above), since the sheet doesn't define them. Tractors use the Misc D column (confidence capped).
- A mapping value ending `_LOWCD2_<n>` puts the RTO in the cluster's "Low CD2 RTOs @ n% CD2" rows. A Low
  CD2 row is otherwise defined only by an "Only for <RTOs>" note; without either it stays `ambiguous`.
- Rows of one cluster limited to named RTOs take precedence over the cluster's general rows, which then
  exclude those RTOs (the sheet's own "All other RTOs of the cluster" note).
- Rows sharing a cluster and segment split by make or body type: an "All"/"Others" row covers what its
  siblings don't name. A body type saying "tanker" without "oil" can't be placed and stays `ambiguous`.
- Comprehensive Max CD2 is one rate for the package: reported as OD, TP unpublished, confidence capped
  (as for Go Digit's two-wheeler and 4W new-business grids).
- A cell with several rates ("52%/44.5%") pairs with a CD1 ladder in column E: the payout depends on the
  OD discount chosen, which the policy doesn't show, so it stays `ambiguous`. "D" declines.
"""

import math
import re
from dataclasses import dataclass, field
from pathlib import Path

from rater.citations import XlsxCite
from rater.grids.adapters.godigit_4w import _pct
from rater.grids.bands import Band
from rater.grids.cvsegments import CvSegment, parse_cv_segment
from rater.grids.makes import canonical_make
from rater.grids.model import (
    Contains,
    ContainsAny,
    DimValue,
    ExceptionRule,
    Grid,
    MappingRow,
    MappingTable,
    NotContainsAny,
    NotIn,
    RateCell,
    RateRule,
    Unpublished,
    norm_key,
)
from rater.grids.textrules import classify
from rater.grids.xlsx import MISSING, Workbook
from rater.resolve.confidence import Cap

INSURER = "Go Digit"
SHEET = "CV Grid (excl. HCV)"
MAP = "CV RTO Mapping"
CLASSES = frozenset({"gcv", "gcv_3w", "pcv_2w", "pcv_3w", "pcv_taxi", "misc_d", "tractor"})
INF = math.inf
PKG_CAP = Cap(
    "medium", "Go Digit CV comprehensive CD2 is one rate for the package; reported as OD, TP unpublished"
)
TRACTOR_CAP = Cap("medium", "tractors placed with the Misc D column of 'CV RTO Mapping' (no tractor column)")

Dims = list[tuple[str, DimValue]]

_COLUMNS: tuple[tuple[str, str, tuple[tuple[str, DimValue], ...], Cap | None], ...] = (
    ("D", "GCV3", (("vehicle_class", "gcv_3w"),), None),
    (
        "E",
        "LCV",
        (("vehicle_class", "gcv"), ("gvw_t", Band(0, 7.5, True, True, "t", "GVW up to 7.5 t"))),
        None,
    ),
    (
        "F",
        "MCV",
        (("vehicle_class", "gcv"), ("gvw_t", Band(7.5, 12, False, True, "t", "GVW 7.5-12 t"))),
        None,
    ),
    (
        "G",
        "HCV",
        (("vehicle_class", "gcv"), ("gvw_t", Band(12, INF, False, True, "t", "GVW over 12 t"))),
        None,
    ),
    ("H", "PCV 2W", (("vehicle_class", "pcv_2w"),), None),
    (
        "H",
        "PCV 3W non-electric",
        (("vehicle_class", "pcv_3w"), ("fuel", NotIn(frozenset({"electric"})))),
        None,
    ),
    ("I", "PCV 3W electric", (("vehicle_class", "pcv_3w"), ("fuel", "electric")), None),
    (
        "J",
        "PCV up to 5 seats",
        (("vehicle_class", "pcv_taxi"), ("seating_capacity", Band(0, 5, True, True, "seats", "up to 5"))),
        None,
    ),
    (
        "K",
        "PCV 6+ seats",
        (("vehicle_class", "pcv_taxi"), ("seating_capacity", Band(6, INF, True, True, "seats", "6+"))),
        None,
    ),
    ("L", "Misc D", (("vehicle_class", "misc_d"),), None),
    ("L", "Misc D (tractor)", (("vehicle_class", "tractor"),), TRACTOR_CAP),
)
_LOW = re.compile(r"_LOWCD2_(\d+(?:\.\d+)?)$", re.I)

# Grid cluster label -> the mapping's spelling. Only spelling differences are bridged ("excl"/"EX",
# "_"/"/", "Vijayawada"/"Vijaywada"; "Kolkata/West Bengal" names two mapping clusters). Labels that differ
# in substance ("KA 1 Good" vs "KA1 (EX BLR)") are not guessed: `unreachable_clusters` reports them.
CLUSTER_ALIASES: dict[str, frozenset[str]] = {
    "NE EXCL ASSAM": frozenset({"NE EX ASSAM"}),
    "GOOD VIZAG_VIJAYAWADA": frozenset({"GOOD VIZAG/VIJAYWADA"}),
    "BAD VIZAG_VIJAYAWADA": frozenset({"BAD VIZAG/VIJAYWADA"}),
    "KOLKATA/WEST BENGAL": frozenset({"KOLKATA", "WEST BENGAL"}),
    # 'HCV GRID' spellings. "KA1"/"KA2" sit beside their own "Bangalore" rows: the mapping's "(EX BLR)".
    "BAD GJ 1& BAD GJ 2": frozenset({"BAD GJ-1", "BAD GJ-2"}),
    "BAD GJ - 1": frozenset({"BAD GJ-1"}),
    "BAD GJ -2": frozenset({"BAD GJ-2"}),
    "KA1": frozenset({"KA1 (EX BLR)"}),
    "KA2": frozenset({"KA2 (EX BLR)"}),
    "GJ REF": frozenset({"GUJARAT REF"}),  # GJ is Gujarat's RTO code
}
_RTO = re.compile(r"\b([A-Z]{2})\s?(\d{1,2})\b")


def _clean(text: object) -> str:
    return " ".join(str(text).split())


def _cluster_keys(label: str) -> frozenset[str]:
    k = _clean(label).upper()
    return CLUSTER_ALIASES.get(k, frozenset({k}))


def _codes(text: str) -> frozenset[str]:
    return frozenset(f"{a}{int(b):02d}" for a, b in _RTO.findall(text.upper()))


# ----------------------------------------------------------------------------------------------- mapping


def _mappings(wb: Workbook, file: str) -> tuple[list[MappingTable], set[str], dict[str, set[str]]]:
    """Tables, every cluster value the mapping uses, and Low CD2 percentages by cluster."""
    sheet = wb.sheet(MAP)
    tables: list[MappingTable] = []
    values: set[str] = set()
    lows: dict[str, set[str]] = {}
    for col, label, when, cap in _COLUMNS:
        clusters, low_rows = [], []
        for r in range(3, sheet.max_row + 1):
            code, v = sheet.value(f"A{r}"), sheet.value(f"{col}{r}")
            if not code or v is None or v is MISSING or _clean(v) in ("", "-", "#N/A"):
                continue
            text = _clean(v).upper()
            m = _LOW.search(text)
            base = text[: m.start()] if m else text
            pct = f"{float(m.group(1)):g}" if m else "no"
            if m:
                lows.setdefault(base, set()).add(pct)
            values.add(base)
            cite = XlsxCite(file, MAP, f"A{r}:{col}{r}")
            clusters.append(MappingRow(_clean(code), base, cite, raw=code, cap=cap))
            low_rows.append(MappingRow(_clean(code), pct, cite, raw=code))
        name = f"Go Digit CV RTO → cluster ({label}, column {col})"
        tables.append(MappingTable(name, "rto", "cluster", tuple(clusters), when=when))
        tables.append(
            MappingTable(
                f"Go Digit CV RTO → Low CD2 marker ({label})", "rto", "low_cd2", tuple(low_rows), when=when
            )
        )
    return tables, values, lows


# ------------------------------------------------------------------------------------------------ cells


@dataclass(frozen=True)
class Part:
    age: Band | None
    percent: float | None
    code: str | None  # "D" / "Declined"


_PART = re.compile(
    r"^\s*(?:age\s*)?(?P<age>.+?)\s*(?:age|years?|yrs?|yr)?\s*"
    r"(?::|-(?=\s*(?:\d+(?:\.\d+)?\s*%|declined)\s*$))\s*(?P<val>\d+(?:\.\d+)?\s*%|declined)\s*$",
    re.I,
)


def _age_band(text: str) -> Band | None:
    t = re.sub(r"\s+", " ", text.lower()).strip()
    t = re.sub(r"\b(?:age|years?|yrs?|yr)\b", "", t).strip()
    if m := re.fullmatch(r">=\s*(\d+)", t):
        return Band(int(m[1]), INF, True, True, "years", text)
    if m := re.fullmatch(r">\s*(\d+)", t):
        return Band(int(m[1]), INF, False, True, "years", text)
    if m := re.fullmatch(r"(\d+)\s*\+", t):
        return Band(int(m[1]), INF, True, True, "years", text)
    if m := re.fullmatch(r"(\d+)\s*(?:-|to)\s*(\d+)", t):
        return Band(int(m[1]), int(m[2]), True, True, "years", text)
    if m := re.fullmatch(r"(\d+)", t):
        return Band(int(m[1]), int(m[1]), True, True, "years", text)
    return None


def _cell(v: object) -> list[Part] | str | None:
    """Rate parts of one cell, a reason it can't be read as one rate per policy, or None when empty."""
    if v is None or v is MISSING:
        return None
    if isinstance(v, int | float):
        return [Part(None, _pct(v), None)]
    s = str(v).strip()
    if s.upper() == "D":
        return [Part(None, None, "D")]
    if "/" in s:
        return f"Max CD2 '{_clean(s)}' gives several rates, depending on the CD1 (OD discount) chosen"
    parts = []
    for line in re.split(r"\n|\s{3,}", s):
        if not line.strip():
            continue
        m = _PART.match(line)
        band = _age_band(m["age"]) if m else None
        if not m or band is None:
            return f"Max CD2 '{_clean(s)}' could not be read as one rate per vehicle age"
        val = m["val"].lower()
        parts.append(
            Part(band, None, "Declined") if val == "declined" else Part(band, float(val.rstrip("% ")), None)
        )
    return parts or None


# ------------------------------------------------------------------------------------------------ makes


@dataclass
class MakeScope:
    dims: Dims = field(default_factory=list)
    kind: str = "all"  # all | others | makes | body | model | age | except | undefined
    names: frozenset[str] = frozenset()
    undefined: str | None = None


def _names(text: str) -> frozenset[str]:
    parts = re.split(r",|\band\b|&", re.sub(r"\*|\bonly\b|\bmake\b", "", text, flags=re.I))
    out = set()
    for p in parts:
        p = p.strip()
        if p:
            out.add("ASHOK LEYLAND" if p.upper() == "AL" else canonical_make(p))
    return frozenset(out)


def _make(text: object) -> MakeScope:
    t = _clean(text or "")
    low = t.lower()
    if low in ("", "all"):
        return MakeScope()
    if m := re.fullmatch(r"(\d+)\s*(\+|-\s*(\d+))?\s*yrs?", low):
        hi: float = INF if m[2] == "+" else (int(m[3]) if m[3] else int(m[1]))
        return MakeScope([("age", Band(int(m[1]), hi, True, True, "years", t))], "age")
    if low in ("high hp", "low hp"):
        return MakeScope(
            kind="undefined", undefined=f"make column '{t}' splits tractors by HP without a threshold"
        )
    if low == "oil tanker":
        return MakeScope([("body_type", ContainsAny(frozenset({"OIL TANKER"})))], "body")
    if low in ("others", "other makes"):
        return MakeScope(kind="others")
    if low == "bajaj re":
        return MakeScope(
            [("make", "BAJAJ")],
            "undefined",
            undefined="make column 'Bajaj RE' names a Bajaj model line, which can't be matched reliably",
        )
    for model_text, make, model in (
        ("tata ace", "TATA", "ACE"),
        ("tata intra", "TATA", "INTRA"),
        ("winger", "TATA", "WINGER"),
    ):
        if low == model_text:
            return MakeScope([("make", make), ("model", Contains(model))], "model")
    if low == "force - pcv":
        return MakeScope([("make", "FORCE")], "makes", frozenset({"FORCE"}))
    if m := re.fullmatch(r"(?:all\s*(?:excluding|excl\.?|\(except)|non[\s-]*)\s*(.+?)\)?", low):
        rest = m[1]
        dims: Dims = []
        body = re.search(r"[/(]\s*non\s*dumper\s*/\s*tipper\)?", rest)
        if body:
            dims.append(("body_type", NotContainsAny(frozenset({"DUMPER", "TIPPER"}))))
            rest = rest[: body.start()]
        names = _names(rest)
        return MakeScope([("make", NotIn(names)), *dims], "except", names)
    names = _names(t)
    if not names:
        return MakeScope(kind="undefined", undefined=f"make column '{t}' could not be read")
    return MakeScope([("make", names if len(names) > 1 else next(iter(names)))], "makes", names)


# ------------------------------------------------------------------------------------------------ notes


@dataclass
class NoteScope:
    dims: Dims = field(default_factory=list)
    rtos: frozenset[str] | None = None  # "Only for <RTOs>"
    cluster: frozenset[str] | None = None  # narrows the row's cluster (Good / Bad Bangalore)
    declines: list[tuple[str, Dims]] = field(default_factory=list)  # (text, extra when)
    other: str | None = None  # text left for `classify`


def _cpa_tppd(low: str) -> tuple[Dims, str]:
    dims: Dims = []
    if re.search(r"with\s*no\s*cpa|without\s*cpa", low):
        dims.append(("cpa_cover", "no"))
    elif re.search(r"with\s*cpa", low):
        dims.append(("cpa_cover", "yes"))
    if re.search(r"with\s*/\s*without\s*tppd", low):
        pass
    elif re.search(r"no\s*tppd|without\s*tppd", low):
        dims.append(("tppd_restricted", "no"))
    elif re.search(r"tppd\s*reduction|with\s*tppd", low):
        dims.append(("tppd_restricted", "yes"))
    rest = re.sub(
        r"(with\s*(no\s*)?|without\s*|and\s*|&\s*|only\s*)?(cpa|(with\s*/\s*without\s*|no\s*)?tppd(\s*reduction)?)",
        " ",
        low,
    )
    return dims, rest


_SCOPE_WORDS = {"only", "for", "rto", "rtos", "rto's", "and", "&", "north", "bengal"}


def _note(text: object) -> NoteScope:
    t = _clean(text or "")
    low = t.lower()
    out = NoteScope()
    if not t:
        return out
    if "body type crane is declined" in low:
        out.declines.append((t, [("body_type", ContainsAny(frozenset({"CRANE"})))]))
        return out
    if low == "all oem except hyundai":
        out.dims.append(("make", NotIn(frozenset({"HYUNDAI"}))))
        return out
    if low == "piaggio make declined":
        out.declines.append((t, [("make", "PIAGGIO")]))
        return out
    if low == "all other rtos of the cluster":
        return out  # the precedence rule below gives these rows their exclusions
    if m := re.fullmatch(r"only for (good|bad) bangalore rtos", low):
        out.cluster = frozenset({f"BANGALORE-{m[1].upper()}"})
        return out
    if low.startswith("declined rtos") or re.fullmatch(r"[a-z]{2}\s?\d{1,2} is declined", low):
        out.declines.append((t, [("rto", _codes(t))]))
        return out
    first, _, after = t.partition(". ")
    flow = first.lower()
    cpa, rest = _cpa_tppd(flow)
    codes = _codes(first)
    words = set(re.sub(r"\b[a-z]{2}\s?\d{1,2}\b|[,.()]", " ", rest).split())
    if codes and re.match(r"\s*(excl(uding)?)\b", flow) and words <= _SCOPE_WORDS | {"excl", "excluding"}:
        out.dims.append(("rto", NotIn(codes)))
    elif codes and words <= _SCOPE_WORDS:
        out.rtos = codes
    elif cpa and words <= _SCOPE_WORDS:
        pass
    else:
        out.other = t
        return out
    out.dims.extend(cpa)
    if after.strip():
        out.other = after.strip()
    return out


# ------------------------------------------------------------------------------------------------- rows


@dataclass
class Row:
    r: int
    cluster: str
    keys: frozenset[str]
    seg: CvSegment
    make: MakeScope
    note: NoteScope
    dims: Dims
    low_pct: str | None = None  # Low CD2 row placed through the mapping's suffix
    undefined: list[tuple[str, str]] = field(default_factory=list)  # (reason, column)

    @property
    def group(self) -> tuple[str, str]:
        return self.cluster.upper(), self.seg.label.lower()


def _overlap(a: Dims, b: Dims) -> bool:
    bm: dict[str, list[DimValue]] = {}
    for d, w in b:
        bm.setdefault(d, []).append(w)
    for d, wa in a:
        for wb in bm.get(d, []):
            if isinstance(wa, Band) and isinstance(wb, Band):
                if wa.hi < wb.lo or wb.hi < wa.lo:
                    return False
            elif isinstance(wa, str | frozenset) and isinstance(wb, str | frozenset):
                sa = {norm_key(x) for x in ([wa] if isinstance(wa, str) else wa)}
                sb = {norm_key(x) for x in ([wb] if isinstance(wb, str) else wb)}
                if not sa & sb:
                    return False
    return True


def _rows(wb: Workbook, lows: dict[str, set[str]]) -> list[Row]:
    sheet = wb.sheet(SHEET)
    rows: list[Row] = []
    last: dict[str, object] = {}  # cluster -> last segment label (merged cells)
    for r in range(4, sheet.max_row + 1):
        cluster = sheet.value(f"B{r}")
        if not cluster:
            continue
        cluster = _clean(cluster)
        seg_text = sheet.value(f"C{r}") or last.get(cluster)
        if not seg_text:
            continue
        last[cluster] = seg_text
        seg = parse_cv_segment(str(seg_text))
        if isinstance(seg, str):
            raise ValueError(f"Go Digit '{SHEET}' row {r}: {seg}")
        make, note = _make(sheet.value(f"D{r}")), _note(sheet.value(f"H{r}"))
        keys = note.cluster or _cluster_keys(cluster)
        row = Row(r, cluster, keys, seg, make, note, [*seg.dims, *make.dims, *note.dims])
        if note.rtos is not None:
            row.dims.append(("rto", note.rtos))
        cd1 = sheet.value(f"E{r}")
        if isinstance(cd1, str) and re.fullmatch(r"\s*\d+(?:\.\d+)?%\s*-\s*\d+(?:\.\d+)?%\s*", cd1):
            row.undefined.append((f"Max CD2 depends on the CD1 (OD discount) band '{_clean(cd1)}'", "E"))
        if make.undefined:
            row.undefined.append((make.undefined, "D"))
        if seg.undefined and not seg.catch_all:
            m = re.search(r"low[\s_]*cd2\s*rtos\s*@\s*(\d+(?:\.\d+)?)\s*%", seg.label, re.I)
            pct = f"{float(m[1]):g}" if m else None
            if note.rtos is not None and m:
                pass  # the note names the Low CD2 RTOs
            elif pct and any(pct in lows.get(k, set()) for k in keys):
                row.low_pct = pct
                row.dims.append(("low_cd2", pct))
            else:
                row.undefined.append((seg.undefined, "C"))
        rows.append(row)
    _precedence(rows, lows)
    return rows


def _precedence(rows: list[Row], lows: dict[str, set[str]]) -> None:
    by_cluster: dict[str, list[Row]] = {}
    for row in rows:
        by_cluster.setdefault(row.cluster.upper(), []).append(row)
    for members in by_cluster.values():
        scoped = [x for x in members if x.note.rtos is not None]
        for row in members:
            if row.note.rtos is None:
                codes = frozenset().union(
                    *(x.note.rtos for x in scoped if x.note.rtos and _overlap(row.dims, x.dims))
                )
                if codes:
                    row.dims.append(("rto", NotIn(codes)))
            low_segment = re.search(r"low[\s_]*cd2", row.seg.label, re.I)
            if not low_segment and any(lows.get(k) for k in row.keys):
                row.dims.append(("low_cd2", "no"))
    groups: dict[tuple[str, str], list[Row]] = {}
    for row in rows:
        groups.setdefault(row.group, []).append(row)
    for members in groups.values():
        named = frozenset().union(*(x.make.names for x in members if x.make.kind == "makes"))
        tanker = any(x.make.kind == "body" for x in members)
        for row in members:
            if row.make.kind in ("all", "others") and named:
                row.dims.append(("make", NotIn(named)))
            if row.make.kind in ("all", "others") and tanker:
                row.dims.append(("body_type", NotContainsAny(frozenset({"TANKER"}))))


def _dims(row: Row, extra: Dims = ()) -> tuple[tuple[str, DimValue], ...]:  # type: ignore[assignment]
    return tuple(sorted([("cluster", row.keys), *row.dims, *extra], key=lambda d: d[0]))


# ------------------------------------------------------------------------------------------------ grids


def _shared_exceptions(rows: list[Row], file: str, declined: set[str]) -> list[ExceptionRule]:
    out: list[ExceptionRule] = []
    for row in rows:
        when = _dims(row)
        for reason, col in row.undefined:
            out.append(
                ExceptionRule(
                    "unclassified",
                    f"{reason} (row {row.r})",
                    XlsxCite(file, SHEET, f"{col}{row.r}"),
                    when=when,
                )
            )
        if row.seg.catch_all:
            out.append(
                ExceptionRule(
                    "catch_all",
                    f"{row.seg.undefined} (row {row.r})",
                    XlsxCite(file, SHEET, f"C{row.r}"),
                    when=when,
                )
            )
        for text, extra in row.note.declines:
            out.append(
                ExceptionRule(
                    "policy_condition",
                    text,
                    XlsxCite(file, SHEET, f"H{row.r}"),
                    effect="decline",
                    when=_dims(row, extra),
                )
            )
        if row.note.other:
            k = classify(row.note.other, "gcv")
            kind = "unclassified" if k.kind in ("policy_condition", "undefined_decline") else k.kind
            out.append(ExceptionRule(kind, k.text, XlsxCite(file, SHEET, f"H{row.r}"), when=when))
    groups = {row.group: row for row in rows if row.make.kind == "body"}
    for row in groups.values():
        base = [(d, w) for d, w in _dims(row) if d != "body_type"]
        out.append(
            ExceptionRule(
                "unclassified",
                f"the body type is a tanker but not stated as an oil tanker; the grid's Oil Tanker row "
                f"(row {row.r}) may or may not apply",
                XlsxCite(file, SHEET, f"D{row.r}"),
                when=tuple(base)
                + (
                    ("body_type", ContainsAny(frozenset({"TANKER"}))),
                    ("body_type", NotContainsAny(frozenset({"OIL TANKER"}))),
                ),
            )
        )
    if declined:
        out.append(
            ExceptionRule(
                "policy_condition",
                "The RTO maps to a declined cluster in 'CV RTO Mapping' ("
                + ", ".join(sorted(declined))
                + ")",
                XlsxCite(file, MAP, "A2:L2"),
                effect="decline",
                when=(("cluster", frozenset(declined)),),
            )
        )
    return out


def _grid_rules(
    wb: Workbook, rows: list[Row], file: str, col: str, component: str
) -> tuple[list[RateRule], list[ExceptionRule]]:
    sheet = wb.sheet(SHEET)
    rules: list[RateRule] = []
    excs: list[ExceptionRule] = []
    for row in rows:
        if row.undefined or row.seg.catch_all:
            continue  # covered by a cited exception
        v = sheet.value(f"{col}{row.r}")
        cite = XlsxCite(file, SHEET, f"{col}{row.r}")
        parts = _cell(v)
        if parts is None:
            continue
        if isinstance(parts, str):
            excs.append(ExceptionRule("unclassified", f"{parts} (row {row.r})", cite, when=_dims(row)))
            continue
        for part in parts:
            extra: Dims = [("age", part.age)] if part.age else []
            when = _dims(row, extra)
            if part.code:
                excs.append(
                    ExceptionRule(
                        "policy_condition",
                        f"The grid gives '{part.code}' instead of a rate",
                        cite,
                        effect="decline",
                        when=when,
                    )
                )
                continue
            assert part.percent is not None
            cell = RateCell(
                part.percent, v, cite, label=f"Max CD2 ({'SATP' if component == 'tp' else 'COMP'})"
            )
            rules.append(
                RateRule(
                    when,
                    cell if component == "od" else None,
                    cell if component == "tp" else None,
                    XlsxCite(file, SHEET, f"B{row.r}:H{row.r}"),
                    f"{row.cluster} · {row.seg.label} · {_clean(sheet.value(f'D{row.r}') or 'All')}"
                    + (f" · age {part.age.label}" if part.age else ""),
                )
            )
    return rules, excs


def unreachable_clusters(grid: Grid) -> set[str]:
    """Grid cluster labels that no `CV RTO Mapping` value reaches (reported, never guessed)."""
    values = {
        norm_key(r.value)
        for t in grid.mappings
        if isinstance(t, MappingTable) and t.target == "cluster"
        for r in t.rows
    }
    out = set()
    for rule in grid.rules:
        keys = rule.dim_map.get("cluster")
        if isinstance(keys, frozenset) and not any(norm_key(k) in values for k in keys):
            out |= set(keys)
    return out


def load(root: Path) -> list[Grid]:
    path = next((root / "raters" / "godigit").rglob("*.xlsx"))
    file = path.relative_to(root).as_posix()
    wb = Workbook(path)
    try:
        tables, values, lows = _mappings(wb, file)
        rows = _rows(wb, lows)
        declined = {v for v in values if "DECLINED" in v}
        shared = _shared_exceptions(rows, file, declined)
        comp, comp_exc = _grid_rules(wb, rows, file, "F", "od")
        satp, satp_exc = _grid_rules(wb, rows, file, "G", "tp")
        from rater.grids.adapters import godigit_hcv  # it reuses this module's helpers

        hcv_comp, hcv_satp = godigit_hcv.load_into(wb, file, lows)
    finally:
        wb.close()
    common = dict(insurer=INSURER, file=file, vehicle_classes=CLASSES, mappings=tuple(tables))
    return [
        Grid(
            id="godigit/CV Comp",
            title=f"Go Digit '{SHEET}' and '{godigit_hcv.SHEET}' (comprehensive)",
            policy_types=frozenset({"comprehensive"}),
            rules=tuple(comp + hcv_comp.rules),
            exceptions=tuple(shared + comp_exc + hcv_comp.exceptions),
            unpublished=(
                Unpublished(
                    "comprehensive",
                    "tp",
                    "Go Digit publishes one CD2 for comprehensive commercial-vehicle policies "
                    "(applied here to OD); no separate TP rate",
                    XlsxCite(file, SHEET, "E2"),
                ),
            ),
            caps=(PKG_CAP,),
            **common,  # type: ignore[arg-type]
        ),
        Grid(
            id="godigit/CV SATP",
            title=f"Go Digit '{SHEET}' and '{godigit_hcv.SHEET}' (SATP)",
            policy_types=frozenset({"satp"}),
            rules=tuple(satp + hcv_satp.rules),
            exceptions=tuple(shared + satp_exc + hcv_satp.exceptions),
            **common,  # type: ignore[arg-type]
        ),
    ]
