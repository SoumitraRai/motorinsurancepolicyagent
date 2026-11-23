"""Go Digit `TAXI Segments and Location wise`, loaded into the Go Digit CV grids."""

import dataclasses
from typing import Any

from rater.bundle import BUNDLE_ROOT
from rater.grids.adapters.godigit_cv import unreachable_clusters
from rater.grids.adapters.godigit_taxi import SHEET, parse_taxi_segment
from rater.grids.model import dim_matches
from rater.grids.xlsx import Workbook
from tests.grids.adapters.test_godigit_cv import grids, run

GODIGIT = next((BUNDLE_ROOT / "raters/godigit").rglob("*.xlsx"))


def taxi(policy_type: str = "comprehensive", **over: Any):  # type: ignore[no-untyped-def]
    base: dict[str, Any] = dict(
        vehicle_class="pcv_taxi",
        make="MARUTI",
        model="DZIRE",
        fuel="petrol",
        cc=1197,
        seating_capacity=5,
        manufacture_year=2023,
        add_ons=["Zero Depreciation"],
        body_type=None,
    )
    base.update(over)
    return run(policy_type, **base)


def cites(r) -> str:  # type: ignore[no-untyped-def]
    return " ".join(x.grid_citation or "" for x in r.rates.values())


def why(r) -> str:  # type: ignore[no-untyped-def]
    return " ".join(s.decision for s in r.trace)


def matches(label: str, **facts: Any) -> bool:
    seg = parse_taxi_segment(label)
    assert not isinstance(seg, str), seg
    return all(d in facts and dim_matches(w, facts[d]) for d, w in seg.dims)


def test_segments() -> None:
    label = "Taxi upto 5 seater non-diesel < 1000 cc"
    assert matches(label, vehicle_class="pcv_taxi", seating_capacity=5, fuel="cng", cc=998)
    assert not matches(label, vehicle_class="pcv_taxi", seating_capacity=5, fuel="diesel", cc=998)
    assert not matches(label, vehicle_class="pcv_taxi", seating_capacity=5, fuel="petrol", cc=1000)
    label = "Taxi upto 5 seater diesel > 1000 cc & <=1500 cc"
    assert matches(label, vehicle_class="pcv_taxi", seating_capacity=5, fuel="diesel", cc=1500)
    assert not matches(label, vehicle_class="pcv_taxi", seating_capacity=5, fuel="diesel", cc=1501)
    label = "Taxi 6-9 seater > 1500 cc 5+ years"
    assert matches(label, vehicle_class="pcv_taxi", seating_capacity=7, cc=2393, age=5)
    assert not matches(label, vehicle_class="pcv_taxi", seating_capacity=7, cc=2393, age=4)
    assert matches("Taxi upto 5 seater non-diesel < 1000 cc Age 0", vehicle_class="pcv_taxi",
                   seating_capacity=4, fuel="petrol", cc=998, age=0)  # fmt: skip
    assert matches("Taxi upto 7 seater CNG > 1000 cc", vehicle_class="pcv_taxi", seating_capacity=7,
                   fuel="cng", cc=1462)  # fmt: skip
    assert isinstance(parse_taxi_segment("Taxi upto 5 seater turbo"), str)


def test_taxi_rules_join_the_cv_grids() -> None:
    for grid in grids().values():
        assert any(rule.cite.sheet == SHEET for rule in grid.rules), grid.id


def test_every_data_row_gives_a_rule_or_a_cited_exception() -> None:
    sheet = Workbook(GODIGIT).sheet(SHEET)
    for grid_id, col in (("godigit/CV Comp", "G"), ("godigit/CV SATP", "H")):
        grid = grids()[grid_id]
        cited = {(r.od or r.tp).cite.range for r in grid.rules if r.cite.sheet == SHEET}  # type: ignore[union-attr]
        cited |= {e.cite.range for e in grid.exceptions if e.cite.sheet == SHEET}
        for r in range(4, sheet.max_row + 1):
            if sheet.value(f"B{r}") and sheet.value(f"{col}{r}") is not None:
                assert f"{col}{r}" in cited, (grid_id, col, r)


def test_every_taxi_cluster_reaches_the_mapping_except_those_not_guessed() -> None:
    grid = grids()["godigit/CV Comp"]
    only = dataclasses.replace(grid, rules=tuple(r for r in grid.rules if r.cite.sheet == SHEET))
    # "KA 2 Bad" and "J&K, Laddakh" are not in the mapping either, but every cell of theirs is "D" (no rule).
    assert unreachable_clusters(only) == {"KA 1 GOOD"}


def test_cc_make_and_add_on_rows() -> None:
    r = taxi(rto="UP32")  # Lucknow, Maruti, > 1000 cc, with add-ons
    assert r.status == "resolved", why(r)
    assert r.rates["od"].rate_percent == 30 and cites(r).endswith(f"'{SHEET}'!G6")
    assert taxi(rto="UP32", cc=998, model="ALTO").rates["od"].rate_percent == 25
    assert taxi(rto="UP32", cc=998, model="TIAGO", make="TATA").rates["od"].rate_percent == 10
    assert taxi("satp", rto="UP32", fuel="diesel").rates["tp"].rate_percent == 2.5
    assert taxi(rto="UP32", fuel="electric", cc=None).status == "ambiguous"  # cc decides the row


def test_exactly_1000_cc_falls_between_the_rows() -> None:
    r = taxi(rto="UP32", cc=1000, model="ALTO K10")
    assert r.status == "ambiguous", why(r)


def test_wagonr_takes_the_over_1000_cc_rows_where_the_sheet_says_so() -> None:
    r = taxi(rto="UP32", cc=998, model="WAGON R")
    assert r.status == "resolved" and r.rates["od"].rate_percent == 30, why(r)
    r = taxi(rto="KA01", cc=998, model="WAGONR VXI")  # Bangalore: Maruti < 1000 cc is declined
    assert r.status == "resolved" and cites(r).endswith("!G107"), why(r)
    assert taxi(rto="KA01", cc=998, model="ALTO").status == "unsupported"


def test_other_means_the_makes_its_siblings_do_not_name() -> None:
    r = taxi(rto="KA01", make="TATA", model="TIGOR", fuel="diesel", cc=1199)
    assert r.status == "unsupported" and "'D'" in why(r)  # Bangalore "Other" diesel 1000-1500 cc
    r = taxi(rto="WB01", make="HINDUSTAN", model="AMBASSADOR", fuel="diesel", cc=1489, add_ons=[])
    assert r.status == "resolved" and r.rates["od"].rate_percent == 45, why(r)
    r = taxi(rto="WB01", make="TATA", model="INDIGO", fuel="diesel", cc=1396)
    assert r.rates["od"].rate_percent == 10  # "Others (Other than Hindustan make)"


def test_make_scopes_with_ages() -> None:
    new = dict(rto="DL01", manufacture_year=2026)  # DELHI-NCR, age 0
    assert taxi(make="HYUNDAI", model="AURA", **new).rates["od"].rate_percent == 15
    assert taxi(**new).rates["od"].rate_percent == 30  # "Maruti Age 0"
    assert taxi(rto="DL01", make="HYUNDAI", model="AURA").rates["od"].rate_percent == 30  # age 3
    r = taxi(rto="DL01", cc=998, model="ALTO")  # "Maruti (all age) & Hyundai age 1+"
    assert r.status == "resolved" and cites(r).endswith("!G536"), why(r)
    assert taxi(rto="DL01", fuel="diesel").status == "unsupported"


def test_kaali_peeli_rows_make_the_rate_unknowable() -> None:
    r = taxi(rto="MH01")  # Mumbai Maruti > 1000 cc with add-ons: G257 25%, Kaali peeli G265 47.5%
    reason = r.trace[-1].decision
    assert r.status == "ambiguous" and "Kaali peeli" in reason and "47.5%" in reason, reason
    assert taxi(rto="MH01", fuel="diesel").rates["od"].rate_percent == 5
    assert taxi(rto="DL01", fuel="cng").status == "ambiguous"  # "Kaali-Peeli (Maruti & Hyundai)" CNG


def test_rows_noted_only_for_named_rtos() -> None:
    r = taxi(rto="WB71", manufacture_year=2026, cc=998, model="ALTO")  # North Bengal-1, age 0
    assert r.status == "resolved" and r.rates["od"].rate_percent == 29, why(r)
    assert taxi("satp", rto="WB71", manufacture_year=2026, cc=998, model="ALTO").status == "unsupported"


def test_rows_noted_only_for_wb01_to_wb10_exclude_other_kolkata_rtos() -> None:
    assert taxi(rto="WB01", cc=998, model="ALTO").rates["od"].rate_percent == 30  # row 40
    r = taxi(rto="WB15", cc=998, model="ALTO")  # mapped to Kolkata, but not WB01-WB10
    assert r.status == "unsupported", why(r)


def test_volume_bonus_note_is_listed_not_applied() -> None:
    r = taxi(rto="JK02")  # Jammu, > 1000 cc, with add-ons: row 155
    assert r.status == "resolved" and r.rates["od"].rate_percent == 35, why(r)
    assert any("volume" in n.rule for n in r.not_applied)
