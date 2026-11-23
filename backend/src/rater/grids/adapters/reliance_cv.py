"""Reliance `FEB'26 - Grid`: commercial vehicles, taxis, three-wheelers, tractors and school buses, with the
`RTO List` RTO → region map and the CV / school-bus / hygiene / synergy terms of `Enabler, PO Guidelines &
T&C`.

One row per RTO region (column C, the `RTO List`'s own region names), one column per segment and
policy type (row 2 segment, row 3 scope, row 4 COMP / STP).

Readings (README assumptions):
- GVW in kg ("2.5K" = 2.5 t). Bands: < 2.0 t; < 2.5 t (others; TATA/Maruti from 2.0 t); 2.5-3.5 t;
  7.5-12 t; 12-20 t, 20-40 t, 40-50 t, over 50 t. 3.5-7.5 t has no column. From 12 t, COMP is only for
  TATA, Ashok Leyland and Eicher; STP is all makes.
- COMP is the package payout on OD (TP unpublished). A 0 is the published payout (0%).
- Taxi "< 6 Seater" = up to 5 seats; "7+1STR" = 8 seats. "Nil Dep" = a zero-depreciation add-on (COMP
  only). Tractor "Fresh" = new business; "without Trailer" = a body type not naming a trailer.
- Kaali Peeli (black-and-yellow taxi) is not a policy fact (`kaali_peeli`): where its rate differs from
  the ordinary taxi rate, the result is `ambiguous`, naming both rates. Flat Bed rows are matched by body
  type, so an unknown body type is `ambiguous` where the Flat Bed rate differs.
- Left out: Employee Pick up and Car Carrier ("Only Deal Based", all 0) and "PC STP Non-Diesel" (all 0;
  private cars are priced by `PRIVATE CAR COMP, SAOD & STP`, so a second private-car grid would clash).
- Terms: M&HCV towing cover (1.5% less without it); the residency clause (2.5% less, applied to every
  heavy goods vehicle: PO decision 2026-11-23); OD discount over 85% (2.5% less; not on the policy, so
  heavy-goods COMP is `ambiguous`); the West Zone booking-location rules
  (`ambiguous` for Ahmedabad, Vadodara, Surat, Pune and Nagpur, over 12 t); no CPA, 1% less. School-bus
  enablers and volume slabs are partner terms: listed, not applied (D2), like synergy.
"""

import math
import re
from dataclasses import dataclass
from pathlib import Path

from rater.citations import XlsxCite
from rater.grids.adapters.reliance_pvtcar import _month_year
from rater.grids.bands import Band
from rater.grids.makes import canonical_make
from rater.grids.model import (
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
)
from rater.grids.textrules import classify
from rater.grids.xlsx import MISSING, Sheet, Workbook

INSURER = "Reliance"
SHEET = "FEB'26 - Grid"
TC = "Enabler, PO Guidelines & T&C"
INF = math.inf
FIRST, LAST = 5, 76

Dims = tuple[tuple[str, DimValue], ...]

REGION_ALIASES = {"TRIVANDRUM": "THIRUVANANTHAPURAM", "LEH & LAHDHK": "LADAKH"}
TATA_MARUTI = frozenset({"TATA", "MARUTI"})
HEAVY_COMP = frozenset({canonical_make(m) for m in ("Tata", "Ashok Leyland", "Eicher")})
OTHER_FUELS = frozenset({"petrol", "cng", "electric"})


def _gvw(lo: float, hi: float, lo_incl: bool, hi_incl: bool, label: str) -> tuple[str, DimValue]:
    return ("gvw_t", Band(lo, hi, lo_incl, hi_incl, "t", label))


def _age(lo: float, hi: float, lo_incl: bool, label: str) -> tuple[str, DimValue]:
    return ("age", Band(lo, hi, lo_incl, True, "years", label))


GCV: tuple[str, DimValue] = ("vehicle_class", "gcv")
TAXI: Dims = (("vehicle_class", "pcv_taxi"), ("seating_capacity", Band(0, 5, True, True, "seats", "< 6")))
TRACTOR: Dims = (("vehicle_class", "tractor"), ("body_type", NotContainsAny(frozenset({"TRAILER"}))))
UP_TO_5 = _age(0, 5, True, "up to 5 years")
OVER_5 = ("age", Band(5, INF, False, True, "years", "above 5 years"))


@dataclass(frozen=True)
class Column:
    col: str
    components: tuple[str, ...]
    alternatives: tuple[Dims, ...]


def _heavy(od: str, tp: str, gvw: tuple[str, DimValue], age: tuple[str, DimValue] | None) -> list[Column]:
    dims: Dims = (GCV, gvw, *((age,) if age else ()))
    return [Column(od, ("od",), ((*dims, ("make", HEAVY_COMP)),)), Column(tp, ("tp",), (dims,))]


def _pair(od: str, tp: str, *alternatives: Dims) -> list[Column]:
    return [Column(od, ("od",), alternatives), Column(tp, ("tp",), alternatives)]


COLUMNS: tuple[Column, ...] = (
    Column("D", ("od", "tp"), ((("vehicle_class", "school_bus"),),)),
    *_pair("E", "F", (GCV, _gvw(0, 2.0, True, False, "< 2.0 t"), ("make", TATA_MARUTI))),
    *_pair(
        "G",
        "H",
        (GCV, _gvw(0, 2.5, True, False, "< 2.5 t"), ("make", NotIn(TATA_MARUTI))),
        (GCV, _gvw(2.0, 2.5, True, False, "2.0-2.5 t"), ("make", TATA_MARUTI)),
    ),
    *_pair("I", "J", (GCV, _gvw(2.5, 3.5, True, True, "2.5-3.5 t"))),
    *_pair("K", "L", (GCV, _gvw(7.5, 12, True, True, "7.5-12 t"))),
    *_heavy("M", "N", _gvw(12, 20, False, True, "12-20 t"), UP_TO_5),
    *_heavy("O", "P", _gvw(12, 20, False, True, "12-20 t"), OVER_5),
    *_heavy("Q", "R", _gvw(20, 40, False, True, "20-40 t"), UP_TO_5),
    *_heavy("S", "T", _gvw(20, 40, False, True, "20-40 t"), OVER_5),
    *_heavy("U", "V", _gvw(40, 50, False, True, "40-50 t"), None),
    *_heavy("W", "X", _gvw(50, INF, False, True, "over 50 t"), None),
    *_pair("Y", "Z", (("vehicle_class", "pcv_3w"), ("fuel", NotIn(frozenset({"diesel"}))))),
    Column("AA", ("od",), ((*TAXI, ("fuel", OTHER_FUELS), ("zero_dep", "no")),)),
    Column("AB", ("tp",), ((*TAXI, ("fuel", OTHER_FUELS)),)),
    Column("AC", ("od",), ((*TAXI, ("fuel", "diesel"), ("zero_dep", "no")),)),
    Column("AD", ("tp",), ((*TAXI, ("fuel", "diesel")),)),
    Column("AE", ("od",), ((*TAXI, ("fuel", OTHER_FUELS), ("zero_dep", "yes")),)),
    *_pair(
        "AF",
        "AG",
        (
            ("vehicle_class", "pcv_taxi"),
            ("seating_capacity", Band(8, 8, True, True, "seats", "7+1")),
            ("make", frozenset({"MARUTI", "TOYOTA", "KIA", "MG"})),
        ),
    ),
    Column("AH", ("od",), ((*TRACTOR, ("business_type", "new")),)),
    Column(
        "AI",
        ("od",),
        ((*TRACTOR, ("business_type", frozenset({"renewal", "rollover"})), _age(0, 5, True, "< 5 years")),),
    ),
    Column(
        "AJ",
        ("od",),
        (
            (
                *TRACTOR,
                ("business_type", frozenset({"renewal", "rollover"})),
                ("age", Band(5, INF, False, True, "years", "> 5 years")),
            ),
        ),
    ),
    Column("AK", ("tp",), (TRACTOR,)),
    *_pair("AN", "AO", (GCV, ("body_type", ContainsAny(frozenset({"FLAT BED", "FLATBED"}))))),
    *_pair(
        "AP",
        "AQ",
        (
            ("vehicle_class", "misc_d"),
            ("make", frozenset(canonical_make(m) for m in ("JCB", "L&T", "Caterpillar"))),
        ),
    ),
)
CLASSES = frozenset(w for c in COLUMNS for alt in c.alternatives for d, w in alt if d == "vehicle_class")  # type: ignore[misc]


def _region(label: object) -> frozenset[str]:
    k = " ".join(str(label).split()).upper()
    return frozenset({k, REGION_ALIASES[k]}) if k in REGION_ALIASES else frozenset({k})


# Taxi columns the Kaali Peeli column (AL, "Comp/STP") is set against.
_TAXI_COLUMNS = ("AA", "AB", "AC", "AD", "AE")


def _kaali(sheet: Sheet, file: str, r: int, region: tuple[str, DimValue]) -> list[tuple[str, ExceptionRule]]:
    """(component, exception) where this row's Kaali Peeli rate differs from an ordinary taxi rate."""
    al = sheet.value(f"AL{r}")
    if not isinstance(al, int | float):
        return []
    kaali = round(float(al) * 100, 6)
    place = " ".join(str(sheet.value(f"C{r}")).split())
    out = []
    for column in (c for c in COLUMNS if c.col in _TAXI_COLUMNS):
        v = sheet.value(f"{column.col}{r}")
        if not isinstance(v, int | float) or round(float(v) * 100, 6) == kaali:
            continue
        rate = round(float(v) * 100, 6)
        text = (
            f"{place}: a Kaali Peeli (black-and-yellow) taxi is paid {kaali:g}% ('{SHEET}'!AL{r}) instead of "
            f"{rate:g}% ('{SHEET}'!{column.col}{r}); the policy does not show whether this taxi is "
            "a Kaali Peeli"
        )
        (component,) = column.components
        for alt in column.alternatives:
            when = tuple(sorted((region, *alt, ("kaali_peeli", "yes")), key=lambda d: d[0]))
            rule = ExceptionRule(
                "policy_condition", text, XlsxCite(file, SHEET, f"AL{r}"), "flat", kaali, when=when,
                components=(component,),
            )  # fmt: skip
            out.append((component, rule))
    return out


def _rules(
    wb: Workbook, file: str
) -> tuple[list[RateRule], list[RateRule], list[ExceptionRule], list[ExceptionRule]]:
    """Rate rules and Kaali Peeli exceptions: (comp rules, SATP rules, comp exceptions, SATP exceptions)."""
    sheet = wb.sheet(SHEET)
    comp: list[RateRule] = []
    satp: list[RateRule] = []
    comp_exc: list[ExceptionRule] = []
    satp_exc: list[ExceptionRule] = []
    for r in range(FIRST, LAST + 1):
        label = sheet.value(f"C{r}")
        if not label:
            continue
        region = ("region", _region(label))
        for component, rule in _kaali(sheet, file, r, region):
            (comp_exc if component == "od" else satp_exc).append(rule)
        for column in COLUMNS:
            v = sheet.value(f"{column.col}{r}")
            if v is None or v is MISSING:
                continue
            cite = XlsxCite(file, SHEET, f"{column.col}{r}")
            heading = " / ".join(
                " ".join(str(sheet.value(f"{column.col}{h}") or "").split())
                for h in (3, 4)
                if sheet.value(f"{column.col}{h}")
            )
            cell = RateCell(round(float(v) * 100, 6), v, cite, label=heading)
            for alt in column.alternatives:
                when = tuple(sorted((region, *alt), key=lambda d: d[0]))
                name = f"{' '.join(str(label).split())} · {heading}"
                for component in column.components:
                    out = comp if component == "od" else satp
                    od, tp = (cell, None) if component == "od" else (None, cell)
                    out.append(RateRule(when, od, tp, XlsxCite(file, SHEET, f"A{r}:C{r}"), name))
    return comp, satp, comp_exc, satp_exc


_HEAVY: Dims = (GCV, _gvw(12, INF, True, True, "12 t and above"))
_WEST_BOOKED = frozenset({"AHMEDABAD", "VADODARA", "SURAT", "PUNE", "NAGPUR"})


def _terms(wb: Workbook, file: str) -> tuple[list[ExceptionRule], list[ExceptionRule]]:
    """(comprehensive, SATP) exceptions from the T&C sheet."""
    sheet = wb.sheet(TC)
    comp: list[ExceptionRule] = []
    satp: list[ExceptionRule] = []
    both = (comp, satp)
    section = ""
    west: list[tuple[str, str]] = []
    for r in range(1, sheet.max_row + 1):
        v = sheet.value(f"A{r}")
        if not v:
            continue
        text = " ".join(str(v).split())
        low = text.lower()
        cite = XlsxCite(file, TC, f"A{r}")
        if low.startswith(
            ("guideline of m&hcv", "guidelines for gcv", "school bus", "* terms", "hygiene")
        ) or low in ("synergy enablers",):
            section = low
            if "volume" in low and "slab" in low and not low.startswith("school bus - volume slab"):
                for out in both:
                    out.append(
                        ExceptionRule("broker_side", text, cite, when=(("vehicle_class", "school_bus"),))
                    )
            continue
        if section.startswith("guideline of m&hcv"):
            if "towing" in low:
                comp.append(
                    ExceptionRule(
                        "policy_condition", text, cite, "reduce", 1.5,
                        when=(*_HEAVY, ("add_ons", NotIn(frozenset({"TOWING"})))), components=("od",),
                    )
                )  # fmt: skip
            elif "odd" in low:
                comp.append(
                    ExceptionRule(
                        "policy_condition", text, cite, "reduce", 2.5,
                        when=(*_HEAVY, ("od_discount", Band(85, INF, False, True, "%", "over 85%"))),
                        components=("od",),
                    )
                )  # fmt: skip
            elif "residency" in low:
                for out in both:
                    out.append(
                        ExceptionRule(
                            "policy_condition", text, cite, "reduce", 2.5,
                            when=_HEAVY,  # applied to every heavy goods vehicle (PO, 2026-11-23)
                        )
                    )  # fmt: skip
        elif section.startswith("guidelines for gcv"):
            west.append((text, f"A{r}"))
        elif section.startswith(("school bus", "* terms")):
            if re.match(r"^(\d+\s*\.|sc\s*>)", low):
                for out in both:
                    out.append(
                        ExceptionRule("broker_side", text, cite, when=(("vehicle_class", "school_bus"),))
                    )
        elif section.startswith("hygiene"):
            if not re.match(r"^\d+\s*\.", low):
                continue
            k = classify(text, "gcv")
            when: Dims = (("cpa_cover", "no"),) if re.search(r"\bcpa\b", low) else ()
            for out in both:
                out.append(ExceptionRule(k.kind, k.text, cite, k.effect, k.percent, when=when))
        elif section == "synergy enablers" and (re.match(r"^\d+\s*\.", low) or "%" in low):
            for out in both:
                out.append(ExceptionRule("broker_side", text, cite))
    if west:
        text = (
            "Guidelines for GCV >12K for West Zone: the payout depends on where the policy is booked, "
            + " ".join(t for t, _ in west)
        )
        rule = ExceptionRule(
            "unclassified",
            text,
            XlsxCite(file, TC, west[0][1]),
            when=(GCV, _gvw(12, INF, False, True, "over 12 t"), ("region", _WEST_BOOKED)),
        )
        for out in both:
            out.append(rule)
    return comp, satp


def _mapping(wb: Workbook, file: str) -> MappingTable:
    sheet = wb.sheet("RTO List")
    rows = []
    for r in range(2, sheet.max_row + 1):
        code, region = sheet.value(f"B{r}"), sheet.value(f"C{r}")
        if not code or not region:
            continue
        cite = XlsxCite(file, "RTO List", f"B{r}:C{r}")
        rows.append(MappingRow(str(code).strip(), " ".join(str(region).split()).upper(), cite, raw=code))
    return MappingTable("Reliance RTO → region (RTO List)", "rto", "region", tuple(rows))


def load(root: Path) -> list[Grid]:
    path = next((root / "raters" / "reliance-indusind").rglob("*.xlsx"))
    file = path.relative_to(root).as_posix()
    wb = Workbook(path)
    try:
        comp, satp, comp_exc, satp_exc = _rules(wb, file)
        comp_terms, satp_terms = _terms(wb, file)
        comp_exc += comp_terms
        satp_exc += satp_terms
        mapping = _mapping(wb, file)
        a1 = str(wb.sheet(SHEET).value("A1"))
    finally:
        wb.close()
    common = dict(
        insurer=INSURER,
        file=file,
        vehicle_classes=CLASSES,
        mappings=(mapping,),
        effective_from=_month_year(a1),
        date_text=a1,
        date_cite=XlsxCite(file, SHEET, "A1"),
    )
    return [
        Grid(
            id="reliance/CV Comp",
            title=f"Reliance '{SHEET}' (comprehensive)",
            policy_types=frozenset({"comprehensive"}),
            rules=tuple(comp),
            exceptions=tuple(comp_exc),
            unpublished=(
                Unpublished(
                    "comprehensive",
                    "tp",
                    "Reliance pays on the OD premium for package policies; no TP rate is published",
                    XlsxCite(file, SHEET, "A2"),
                ),
            ),
            **common,  # type: ignore[arg-type]
        ),
        Grid(
            id="reliance/CV SATP",
            title=f"Reliance '{SHEET}' (SATP)",
            policy_types=frozenset({"satp"}),
            rules=tuple(satp),
            exceptions=tuple(satp_exc),
            **common,  # type: ignore[arg-type]
        ),
    ]
