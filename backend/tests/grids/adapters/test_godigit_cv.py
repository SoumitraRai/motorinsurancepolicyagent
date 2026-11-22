import re
from datetime import date
from typing import Any

from rater.bundle import BUNDLE_ROOT
from rater.grids.adapters.godigit_cv import CLASSES, CLUSTER_ALIASES, SHEET, load, unreachable_clusters
from rater.grids.model import GridSet, MappingTable
from rater.grids.readback import check
from rater.grids.xlsx import Workbook
from rater.resolve.engine import resolve
from rater.switches import Switches
from tests.resolve.conftest import facts

GODIGIT = next((BUNDLE_ROOT / "raters/godigit").rglob("*.xlsx"))
_GRIDS: dict[str, Any] | None = None


def grids() -> dict[str, Any]:
    global _GRIDS
    if _GRIDS is None:
        _GRIDS = {g.id: g for g in load(BUNDLE_ROOT)}
    return _GRIDS


def run(policy_type: str = "comprehensive", **over: Any):  # type: ignore[no-untyped-def]
    base: dict[str, Any] = dict(
        insurer="Go Digit General Insurance Ltd",
        policy_type=policy_type,
        manufacture_year=2022,
        policy_start_date=date(2026, 3, 1),
        business_type="renewal",
        make="TATA",
        model="SIGNA 1923",
        body_type="CLOSED BODY",
        fuel="diesel",
    )
    base.update(over)
    gs = GridSet(grids=tuple(grids().values()), aliases={"Go Digit": ("digit",)})
    return resolve(facts(**{k: v for k, v in base.items() if v is not None}), gs, Switches(), "p.pdf")


def test_grids_and_scope() -> None:
    g = grids()
    assert set(g) == {"godigit/CV Comp", "godigit/CV SATP"}
    assert g["godigit/CV Comp"].policy_types == {"comprehensive"}
    assert g["godigit/CV SATP"].policy_types == {"satp"}
    for grid in g.values():
        assert grid.vehicle_classes == CLASSES
        assert {t.target for t in grid.mappings} == {"cluster", "low_cd2"}


def test_every_citation_reads_back() -> None:
    for grid in grids().values():
        for rule in grid.rules:
            for cell in (rule.od, rule.tp):
                if cell is not None:
                    assert check(BUNDLE_ROOT, cell.cite, cell.raw), (grid.id, cell.cite)
        for table in grid.mappings:
            assert isinstance(table, MappingTable)
            for row in table.rows:
                assert check(BUNDLE_ROOT, row.cite, row.raw), row.cite


def test_every_data_row_gives_a_rule_or_a_cited_exception() -> None:
    sheet = Workbook(GODIGIT).sheet("CV Grid (excl. HCV)")
    for grid_id, col in (("godigit/CV Comp", "F"), ("godigit/CV SATP", "G")):
        grid = grids()[grid_id]
        cited = {r.od.cite.range if r.od else r.tp.cite.range for r in grid.rules}  # type: ignore[union-attr]
        cited |= {e.cite.range for e in grid.exceptions}
        rows = {
            int(re.sub(r"^[A-Z]+", "", e.cite.range.split(":")[0]))
            for e in grid.exceptions
            if e.cite.sheet == SHEET
        }
        for r in range(4, sheet.max_row + 1):
            if sheet.value(f"B{r}") and sheet.value(f"{col}{r}") is not None:
                assert f"{col}{r}" in cited or r in rows, (grid_id, r)


def test_cluster_aliases_only_bridge_spelling() -> None:
    # Each alias differs from the mapping's spelling only in punctuation, "excl"/"ex", or one letter.
    assert CLUSTER_ALIASES["NE EXCL ASSAM"] == frozenset({"NE EX ASSAM"})
    assert CLUSTER_ALIASES["KOLKATA/WEST BENGAL"] == frozenset({"KOLKATA", "WEST BENGAL"})
    # Labels that differ in substance are not bridged; they are reported instead.
    assert {"KA 1 GOOD", "KA 2 BAD"} <= unreachable_clusters(grids()["godigit/CV Comp"])


def test_goods_vehicle_age_split_cell_by_make() -> None:
    r = run(vehicle_class="gcv", rto="DL01", gvw=2400, make="TATA", manufacture_year=2022)  # age 4
    assert r.status == "resolved", r.trace[-1].decision
    assert r.rates["od"].grid_citation.endswith("'CV Grid (excl. HCV)'!F731")
    assert r.rates["tp"].applicable and r.rates["tp"].rate_percent is None


def test_goods_vehicle_needs_gvw_to_pick_the_mapping_column() -> None:
    r = run(vehicle_class="gcv", rto="DL01", gvw=None)
    assert r.status == "ambiguous" and "gvw" in r.trace[-1].decision


def test_body_type_unknown_is_ambiguous_where_an_oil_tanker_row_exists() -> None:
    r = run(vehicle_class="gcv", rto="BR01", gvw=9000, body_type=None)
    assert r.status == "ambiguous" and "body_type" in r.trace[-1].decision
    r = run(vehicle_class="gcv", rto="BR01", gvw=9000, body_type="OIL TANKER")
    assert r.status == "resolved" and r.rates["od"].grid_citation.endswith("!F480")
    r = run(vehicle_class="gcv", rto="BR01", gvw=9000, body_type="TANKER")
    assert r.status == "ambiguous" and "oil tanker" in r.trace[-1].decision


def test_mapping_cluster_the_grid_does_not_name_is_unsupported() -> None:
    r = run(vehicle_class="gcv", rto="DL01", gvw=9000)  # MCV column says "DELHI-1"; the grid has "Delhi"
    assert r.status == "unsupported" and "DELHI-1" in " ".join(s.decision for s in r.trace)


def test_low_cd2_suffix_in_mapping_selects_the_low_cd2_row() -> None:
    r = run(vehicle_class="gcv", rto="AP05", gvw=16000, make="ASHOK LEYLAND", manufacture_year=2018)
    assert r.status == "resolved", r.trace[-1].decision
    assert r.rates["od"].grid_citation.endswith("!F759")


def test_crane_is_declined() -> None:
    r = run(vehicle_class="misc_d", rto="DL01", body_type="CRANE", make="ACE")
    assert r.status == "unsupported" and "CRANE" in r.trace[-1].decision


def test_electric_three_wheeler_column_depends_on_fuel() -> None:
    r = run(vehicle_class="pcv_3w", rto="DL01", fuel=None, make="MAHINDRA")
    assert r.status == "ambiguous" and "fuel" in r.trace[-1].decision


def test_satp_od_not_applicable() -> None:
    r = run(policy_type="satp", vehicle_class="gcv", rto="DL01", gvw=2400)
    assert r.rates["od"].applicable is False
