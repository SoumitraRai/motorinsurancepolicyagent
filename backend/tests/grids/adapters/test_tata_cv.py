"""Tata AIG `CV` standard grid."""

from datetime import date
from typing import Any

from openpyxl.utils import get_column_letter

from rater.bundle import BUNDLE_ROOT
from rater.grids.adapters.tata_cv_tw import load_cv
from rater.grids.model import GridSet
from rater.grids.readback import check
from rater.grids.xlsx import Workbook
from rater.resolve.engine import resolve
from rater.switches import Switches
from tests.resolve.conftest import facts

TATA = next((BUNDLE_ROOT / "raters/tata-aig").rglob("*.xlsx"))
_GRID: Any = None


def grid() -> Any:
    global _GRID
    if _GRID is None:
        _GRID = load_cv(BUNDLE_ROOT)
    return _GRID


def run(policy_type: str = "comprehensive", **over: Any):  # type: ignore[no-untyped-def]
    base: dict[str, Any] = dict(
        insurer="Tata AIG General Insurance",
        policy_type=policy_type,
        vehicle_class="gcv",
        rto_location="MUMBAI",
        manufacture_year=2023,
        policy_start_date=date(2026, 3, 10),
        business_type="renewal",
        make="TATA",
        model="ACE",
        fuel="diesel",
        gvw=2000,
    )
    base.update(over)
    gs = GridSet(grids=(grid(),), aliases={"Tata AIG": ("tata aig",)})
    return resolve(facts(**{k: v for k, v in base.items() if v is not None}), gs, Switches(), "p.pdf")


def why(r) -> str:  # type: ignore[no-untyped-def]
    return " ".join(s.decision for s in r.trace)


def cites(r) -> str:  # type: ignore[no-untyped-def]
    return " ".join(x.grid_citation or "" for x in r.rates.values())


def test_grid_scope_and_date() -> None:
    g = grid()
    assert g.id == "tata-aig/CV"
    assert g.policy_types == {"comprehensive", "satp"}
    assert {
        "gcv",
        "gcv_3w",
        "pcv_2w",
        "pcv_3w",
        "pcv_taxi",
        "school_bus",
        "staff_bus",
        "misc_d",
        "tractor",
    } == (g.vehicle_classes)
    assert g.effective_from == date(2025, 11, 1)


def test_every_citation_reads_back() -> None:
    for rule in grid().rules:
        cell = rule.od or rule.tp
        assert check(BUNDLE_ROOT, cell.cite, cell.raw), cell.cite


def test_every_rate_cell_gives_a_rule_except_unread_segments() -> None:
    sheet = Workbook(TATA).sheet("CV")
    cited = {(r.od or r.tp).cite.range for r in grid().rules}
    for r in range(6, 122):
        seg = str(sheet.value(f"B{r}") or "")
        if not seg or seg in ("Trade Road Risk", "Trailer"):
            continue
        for c in range(6, 65):
            col = get_column_letter(c)
            if isinstance(sheet.value(f"{col}{r}"), int | float):
                assert f"{col}{r}" in cited, f"{col}{r}"
    assert any("Trade Road Risk" in n for n in grid().notes)


def test_goods_vehicles_by_weight_and_age() -> None:
    r = run(business_type="new", manufacture_year=2026)
    assert r.status == "resolved" and cites(r).endswith("'CV'!AE6"), why(r)
    assert r.rates["od"].rate_percent == 58.5 and r.rates["tp"].rate_percent is None
    assert run(gvw=16000).rates["od"].rate_percent == 15.5  # age 3: ">=1<=6"
    assert run(gvw=16000, manufacture_year=2018).rates["od"].rate_percent == 22.5  # age 8: ">6"
    r = run("satp", gvw=16000)
    assert r.status == "resolved" and cites(r).endswith("!AE35"), why(r)


def test_three_wheelers_by_fuel() -> None:
    r = run(vehicle_class="pcv_3w", fuel="cng", gvw=None)
    assert r.status == "resolved" and cites(r).endswith("!AE111"), why(r)
    r = run(vehicle_class="pcv_3w", fuel="petrol", gvw=None)
    assert cites(r).endswith("!AE113"), why(r)  # "Other Than Diesel"


def test_buses_and_taxis_by_seats() -> None:
    r = run(vehicle_class="school_bus", seating_capacity=40, gvw=None)
    assert r.status == "resolved" and cites(r).endswith("!AE75"), why(r)
    assert cites(run(vehicle_class="school_bus", seating_capacity=8, gvw=None)).endswith("!AE68")  # 4W School
    assert cites(run(vehicle_class="staff_bus", seating_capacity=20, gvw=None)).endswith("!AE70")
    assert cites(run(vehicle_class="pcv_taxi", seating_capacity=20, gvw=None)).endswith("!AE70")  # a bus
    assert cites(run(vehicle_class="pcv_taxi", seating_capacity=5, gvw=None)).endswith("!AE67")


def test_misc_harvester_and_tractor() -> None:
    misc = dict(vehicle_class="misc_d", gvw=None)
    assert cites(run(body_type="COMBINE HARVESTER", **misc)).endswith("!AE77")
    assert cites(run(body_type="CRANE", **misc)).endswith("!AE65")
    assert cites(run(vehicle_class="tractor", gvw=None)).endswith("!AE78")


def test_cluster_comes_from_the_printed_rto_location() -> None:
    r = run(rto_location=None)
    assert r.status == "ambiguous" and "rto_location" in why(r), why(r)
