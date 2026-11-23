"""Reliance `FEB'26 - Grid` (commercial vehicles, taxis, school buses) with the `RTO List` map."""

from datetime import date
from typing import Any

from rater.bundle import BUNDLE_ROOT
from rater.grids.adapters.reliance_cv import COLUMNS, SHEET, load
from rater.grids.model import GridSet, MappingTable
from rater.grids.readback import check
from rater.grids.xlsx import Workbook
from rater.resolve.engine import resolve
from rater.switches import Switches
from tests.resolve.conftest import facts

RELIANCE = next((BUNDLE_ROOT / "raters/reliance-indusind").rglob("*.xlsx"))
_GRIDS: dict[str, Any] | None = None


def grids() -> dict[str, Any]:
    global _GRIDS
    if _GRIDS is None:
        _GRIDS = {g.id: g for g in load(BUNDLE_ROOT)}
    return _GRIDS


def run(policy_type: str = "comprehensive", **over: Any):  # type: ignore[no-untyped-def]
    base: dict[str, Any] = dict(
        insurer="Reliance General Insurance",
        policy_type=policy_type,
        vehicle_class="gcv",
        rto="MH01",
        manufacture_year=2023,
        policy_start_date=date(2026, 2, 10),
        business_type="renewal",
        make="TATA",
        model="ACE",
        fuel="diesel",
        gvw=1800,
        body_type="CLOSED BODY",
        add_ons=[],
        cpa_cover="yes",
    )
    base.update(over)
    gs = GridSet(grids=tuple(grids().values()), aliases={"Reliance": ("reliance",)})
    return resolve(facts(**{k: v for k, v in base.items() if v is not None}), gs, Switches(), "p.pdf")


def why(r) -> str:  # type: ignore[no-untyped-def]
    return " ".join(s.decision for s in r.trace)


def cites(r) -> str:  # type: ignore[no-untyped-def]
    return " ".join(x.grid_citation or "" for x in r.rates.values())


def test_grids_and_scope() -> None:
    g = grids()
    assert set(g) == {"reliance/CV Comp", "reliance/CV SATP"}
    for grid in g.values():
        assert "private_car" not in grid.vehicle_classes  # the PC STP columns are all 0 and left out
        assert {"gcv", "pcv_3w", "pcv_taxi", "tractor", "misc_d", "school_bus"} <= grid.vehicle_classes
        assert grid.effective_from == date(2026, 2, 1)


def test_every_citation_reads_back() -> None:
    for grid in grids().values():
        for rule in grid.rules:
            cell = rule.od or rule.tp
            assert check(BUNDLE_ROOT, cell.cite, cell.raw), cell.cite
        for table in grid.mappings:
            assert isinstance(table, MappingTable)
            for row in table.rows:
                assert check(BUNDLE_ROOT, row.cite, row.raw), row.cite


def test_every_loaded_cell_gives_a_rule() -> None:
    sheet = Workbook(RELIANCE).sheet(SHEET)
    cited = {(r.od or r.tp).cite.range for g in grids().values() for r in g.rules}
    for col in {c.col for c in COLUMNS}:
        for r in range(5, 77):
            if sheet.value(f"{col}{r}") is not None:
                assert f"{col}{r}" in cited, f"{col}{r}"


def test_light_goods_vehicles_by_weight_and_make() -> None:
    r = run()  # 1.8 t TATA, Mumbai
    assert r.status == "resolved" and r.rates["od"].rate_percent == 66, why(r)
    assert cites(r).endswith(f"'{SHEET}'!E5")
    assert run("satp").rates["tp"].rate_percent == 66
    assert run(gvw=2200).rates["od"].rate_percent == 65  # TATA 2.0-2.5 t: column G
    assert run(make="MAHINDRA", model="SUPRO", gvw=1800).rates["od"].rate_percent == 65  # "Others"
    r = run(gvw=5000)  # 3.5-7.5 t has no column
    assert r.status in ("unsupported", "ambiguous") and r.rates["od"].rate_percent is None


def rules_at(grid_id: str, cell: str) -> list[Any]:
    return [r for r in grids()[grid_id].rules if (r.od or r.tp).cite.range == cell]


def test_heavy_goods_bands_by_age_and_comp_only_for_named_makes() -> None:
    (satp,) = rules_at("reliance/CV SATP", "N5")  # 12-20 t, up to 5 years, all makes
    dims = dict(satp.dims)
    assert satp.tp.percent == 25 and dims["age"].contains(5) and not dims["age"].contains(6)
    assert "make" not in dims and dims["gvw_t"].contains(20) and not dims["gvw_t"].contains(12)
    (comp,) = rules_at("reliance/CV Comp", "M5")
    assert dict(comp.dims)["make"] == {"TATA", "ASHOK LEYLAND", "EICHER"}
    r = run(make="VOLVO", gvw=16000, model="FM")
    assert r.status == "unsupported", why(r)


def test_heavy_goods_depend_on_terms_the_policy_does_not_show() -> None:
    r = run(gvw=16000, model="SIGNA")
    assert r.status == "ambiguous" and ("od_discount" in why(r) or "residency" in why(r)), why(r)
    r = run("satp", gvw=16000, model="SIGNA")
    assert r.status == "ambiguous" and "residency" in why(r), why(r)


def test_west_zone_booking_location_rules() -> None:
    for grid in grids().values():
        (rule,) = [e for e in grid.exceptions if "booked" in e.text]
        assert rule.kind == "unclassified" and "NAGPUR" in dict(rule.when)["region"]
        assert "MUMBAI" not in dict(rule.when)["region"]


def test_taxi_kaali_peeli_column_makes_the_rate_unknowable_where_it_differs() -> None:
    taxi = dict(vehicle_class="pcv_taxi", make="MARUTI", model="DZIRE", fuel="petrol", seating_capacity=5)
    r = run(**taxi)
    assert r.status == "ambiguous" and "kaali_peeli" in why(r), why(r)


def test_taxi_nil_dep_and_fuel_columns() -> None:
    taxi = dict(vehicle_class="pcv_taxi", make="MARUTI", model="DZIRE", seating_capacity=5, rto="KL02")
    # Kerala: every taxi column is 0, Kaali Peeli too, so no split
    r = run(fuel="petrol", add_ons=["Nil Depreciation"], **taxi)
    assert r.status == "resolved" and cites(r).endswith("!AE31"), why(r)
    r = run(fuel="diesel", **taxi)
    assert r.status == "resolved" and cites(r).endswith("!AC31"), why(r)


def test_three_wheeler_school_bus_misc_and_tractor() -> None:
    r = run(vehicle_class="pcv_3w", make="BAJAJ", model="RE", fuel="cng", gvw=None)
    assert r.rates["od"].rate_percent == 57.5, why(r)
    r = run(vehicle_class="school_bus", make="TATA", model="STARBUS", gvw=None, seating_capacity=40)
    assert r.rates["od"].rate_percent == 71, why(r)
    assert (
        run("satp", vehicle_class="school_bus", gvw=None, seating_capacity=40).rates["tp"].rate_percent == 71
    )
    r = run(vehicle_class="misc_d", make="JCB", model="3DX", gvw=None, body_type="BACKHOE LOADER")
    assert r.rates["od"].rate_percent == 40, why(r)
    tractor = dict(vehicle_class="tractor", make="MAHINDRA", model="575", gvw=None, body_type="TRACTOR")
    r = run(business_type="new", manufacture_year=2026, **tractor)  # "Comp (Fresh)"
    assert r.rates["od"].rate_percent == 25, why(r)
    assert run(**{**tractor, "body_type": None}).status == "ambiguous"  # with or without a trailer


def test_region_spellings_and_flat_bed() -> None:
    r = run(vehicle_class="school_bus", rto="KL01", gvw=None, seating_capacity=40)  # Trivandrum
    assert r.status == "resolved" and cites(r).endswith("!D34"), why(r)
    r = run("satp", gvw=30000, model="SIGNA", body_type=None)  # Flat Bed 0 vs the 20-40 t rate
    assert r.status == "ambiguous" and "body_type" in why(r), why(r)


def test_cpa_missing_reduces_and_bonuses_are_listed() -> None:
    r = run(cpa_cover="no")
    assert r.status == "resolved" and r.rates["od"].rate_percent == 65, why(r)
    r = run(vehicle_class="school_bus", gvw=None, seating_capacity=40)
    assert any("Enabler" in n.rule or "Volume" in n.rule or "volume" in n.rule for n in r.not_applied)
