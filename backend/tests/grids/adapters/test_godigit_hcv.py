"""Go Digit `HCV GRID` (goods vehicles over 12 t), loaded into the Go Digit CV grids."""

import dataclasses
import re
from typing import Any

from rater.bundle import BUNDLE_ROOT
from rater.grids.adapters.godigit_cv import CLUSTER_ALIASES, unreachable_clusters
from rater.grids.adapters.godigit_hcv import SHEET, blocks
from rater.grids.xlsx import Workbook
from tests.grids.adapters.test_godigit_cv import grids, run

GODIGIT = next((BUNDLE_ROOT / "raters/godigit").rglob("*.xlsx"))


def hcv(policy_type: str = "comprehensive", **over: Any):  # type: ignore[no-untyped-def]
    base: dict[str, Any] = dict(
        vehicle_class="gcv", gvw=16000, make="ASHOK LEYLAND", manufacture_year=2022, add_ons=[]
    )
    base.update(over)
    return run(policy_type, **base)


def cites(r) -> str:  # type: ignore[no-untyped-def]
    return " ".join(x.grid_citation or "" for x in r.rates.values())


def why(r) -> str:  # type: ignore[no-untyped-def]
    return " ".join(s.decision for s in r.trace)


def test_hcv_rules_join_the_cv_grids() -> None:
    for grid in grids().values():
        assert any(rule.cite.sheet == SHEET for rule in grid.rules), grid.id


def test_blocks_follow_each_header() -> None:
    sheet = Workbook(GODIGIT).sheet(SHEET)
    found = blocks(sheet)
    assert [b.body for b in found[0].bodies] == [
        "Non-Dumper/Tipper",
        "Dumper/Tipper",
        "Port Trailer",
        "Oil Tanker",
        "Gas Tanker",
    ]
    assert [(b.body, b.col) for b in found[1].bodies] == [
        ("Non-Dumper/Tipper", "F"),
        ("Dumper/Tipper", "K"),
        ("Oil Tanker", "P"),
        ("Gas Tanker", "U"),
    ]
    assert len(found) == 19  # the "Cluster" header of 'Additional Comments' starts no block


def test_every_data_row_gives_a_rule_or_a_cited_exception() -> None:
    sheet = Workbook(GODIGIT).sheet(SHEET)
    for grid_id, offset in (("godigit/CV Comp", 2), ("godigit/CV SATP", 4)):
        grid = grids()[grid_id]
        cited = {(r.od or r.tp).cite.range for r in grid.rules if r.cite.sheet == SHEET}  # type: ignore[union-attr]
        rows = {
            int(re.sub(r"^[A-Z]+", "", e.cite.range.split(":")[0]))
            for e in grid.exceptions
            if e.cite.sheet == SHEET
        }
        referred = {int(re.sub(r"^[A-Z]+", "", r.cite.range.split(":")[0])) for r in grid.rules}
        for block in blocks(sheet):
            for r in block.rows:
                for body in block.bodies:
                    col = body.column(offset)
                    if sheet.value(f"{col}{r}") is not None:
                        assert f"{col}{r}" in cited or r in rows or r in referred, (grid_id, col, r)


def test_comprehensive_and_satp_by_body_type() -> None:
    r = hcv(rto="DD01", body_type="CLOSED BODY")  # Good GJ, 12-20 t, age 4
    assert r.status == "resolved", why(r)
    assert r.rates["od"].rate_percent == 18 and cites(r).endswith("'HCV GRID'!H5")
    assert r.rates["tp"].applicable and r.rates["tp"].rate_percent is None
    r = hcv("satp", rto="DD01", body_type="CLOSED BODY")
    assert r.rates["tp"].rate_percent == 26
    assert hcv(rto="DD01", body_type="TIPPER").rates["od"].rate_percent == 25
    assert hcv(rto="DD01", body_type="OIL TANKER").rates["od"].rate_percent == 20


def test_tanker_neither_oil_nor_gas_is_ambiguous() -> None:
    r = hcv(rto="DD01", body_type="TANKER")
    assert r.status == "ambiguous" and "tanker" in why(r).lower()


def test_young_tanker_is_referred_to_the_non_dumper_tipper_rate() -> None:
    r = hcv(rto="DD01", body_type="OIL TANKER", manufacture_year=2025)  # age 1
    assert r.status == "resolved", why(r)
    assert cites(r).endswith("!H4")


def test_tata_row_overrides_all_makes_only_at_its_ages() -> None:
    new = dict(manufacture_year=2026, rto="DD01", body_type="CLOSED BODY")  # age 0
    r = hcv(make="TATA", **new)  # "With Addon: 15%/10% / Without Addon: 10%"
    assert r.status == "resolved" and r.rates["od"].rate_percent == 10, why(r)
    r = hcv(make="TATA", add_ons=["Zero Depreciation"], **new)
    assert r.status == "ambiguous" and "CD1" in why(r)
    assert hcv(**new).rates["od"].rate_percent == 2.5  # non-TATA: the All row
    r = hcv(make="TATA", rto="DD01", body_type="CLOSED BODY", manufacture_year=2025)  # age 1: All row
    assert r.status == "resolved" and cites(r).endswith("!H4")


def test_tata_row_that_refers_to_all_makes_uses_the_all_row() -> None:
    r = hcv(make="TATA", rto="JH01", body_type="TIPPER", manufacture_year=2026)
    assert r.status == "resolved", why(r)
    assert cites(r).endswith("!M82") and r.rates["od"].rate_percent == 30


def test_volvo_and_scania_are_blocked() -> None:
    r = hcv(make="VOLVO", rto="MH01", body_type="CLOSED BODY", manufacture_year=2025)
    assert r.status == "unsupported" and "Volvo" in why(r)
    r = hcv(make="SCANIA", rto="DD01", body_type="CLOSED BODY", business_type="rollover")
    assert r.status == "unsupported"
    # Good GJ's note keeps renewals going at CD2 - 2.5%, against 'Additional Notes' ("Blocked").
    r = hcv(make="SCANIA", rto="DD01", body_type="CLOSED BODY", business_type="renewal")
    assert r.status == "ambiguous" and "Rene" in why(r)


def test_north_bengal_rate_only_where_the_cell_names_it() -> None:
    old = dict(manufacture_year=2018, body_type="CLOSED BODY")  # row 101: 12-20 t, 6+ years
    r = hcv("satp", rto="WB59", **old)
    assert r.status == "resolved" and r.rates["tp"].rate_percent == 25, why(r)
    assert hcv("satp", rto="WB11", **old).rates["tp"].rate_percent == 17.5
    r = hcv(rto="WB59", **old)  # comprehensive cell splits by make only
    assert r.status == "ambiguous" and "North Bengal" in why(r)
    assert hcv(rto="WB11", make="TATA", **old).rates["od"].rate_percent == 17


def test_nl_registered_vehicles_depend_on_address_proof() -> None:
    r = hcv(rto="NL01", body_type="CLOSED BODY")
    assert r.status == "ambiguous" and "NL RTO" in why(r)


def test_additional_comment_contradicting_the_row_is_ambiguous() -> None:
    r = hcv(rto="GJ02", body_type="CLOSED BODY", manufacture_year=2019)  # Bad GJ-1, age 7
    assert r.status == "ambiguous" and "contradicts" in why(r)
    r = hcv(rto="GJ02", body_type="CLOSED BODY", manufacture_year=2021)  # age 5: row 19 only
    assert r.status == "resolved" and r.rates["od"].rate_percent == 10


def test_mapping_low_cd2_code_without_rows_is_ambiguous() -> None:
    r = hcv(rto="CG04", body_type="CLOSED BODY")  # 'CV RTO Mapping' HCV column: LOWCD2_12TO20_10
    assert r.status == "ambiguous" and "LOWCD2_12TO20_10" in why(r)


def test_low_cd2_suffix_keeps_the_cv_grid_row() -> None:
    r = run(vehicle_class="gcv", rto="AP05", gvw=16000, make="ASHOK LEYLAND", manufacture_year=2018)
    assert r.status == "resolved" and "'HCV GRID'" not in cites(r), why(r)


def test_cell_split_by_tonnage_and_by_age() -> None:
    young = dict(rto="BR01", body_type="TIPPER", manufacture_year=2025)  # Bihar 40T+, age 1
    assert hcv(gvw=42000, **young).rates["od"].rate_percent == 25
    assert hcv(gvw=46000, **young).rates["od"].rate_percent == 2.5
    vizag = dict(rto="AP06", gvw=30000, body_type="CLOSED BODY")  # row 325 SATP
    assert hcv("satp", manufacture_year=2018, **vizag).rates["tp"].rate_percent == 35  # age 8
    r = hcv("satp", manufacture_year=2016, **vizag)  # age 10: both "6-10" and "10+"
    assert r.status == "ambiguous", why(r)


def test_a_row_with_no_single_rate_is_named_not_reported_as_a_gap() -> None:
    r = hcv(rto="MH01", body_type="CLOSED BODY")  # Mumbai 12-20 t, age 4: row 387 is "22.0%/9.5%"
    assert r.status == "ambiguous" and "CD1" in r.trace[-1].decision, why(r)


def test_every_hcv_cluster_reaches_the_mapping() -> None:
    grid = grids()["godigit/CV Comp"]
    hcv_only = dataclasses.replace(grid, rules=tuple(r for r in grid.rules if r.cite.sheet == SHEET))
    assert unreachable_clusters(hcv_only) == set()
    assert CLUSTER_ALIASES["GJ REF"] == frozenset({"GUJARAT REF"})  # GJ: Gujarat's RTO code
    assert CLUSTER_ALIASES["KA1"] == frozenset({"KA1 (EX BLR)"})  # the block has its own Bangalore rows
