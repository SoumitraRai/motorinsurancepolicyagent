"""Go Digit `School & Staff Bus ` with its `School & Staff Bus RTO` map."""

import re
from datetime import date
from typing import Any

from rater.bundle import BUNDLE_ROOT
from rater.grids.adapters.godigit_bus import MAP, SHEET, load
from rater.grids.model import GridSet, MappingTable
from rater.grids.readback import check
from rater.grids.xlsx import Workbook
from rater.resolve.engine import resolve
from rater.switches import Switches
from tests.resolve.conftest import facts

GODIGIT = next((BUNDLE_ROOT / "raters/godigit").rglob("*.xlsx"))
_GRIDS: list[Any] | None = None


def grids() -> list[Any]:
    global _GRIDS
    if _GRIDS is None:
        _GRIDS = load(BUNDLE_ROOT)
    return _GRIDS


def run(policy_type: str = "comprehensive", **over: Any):  # type: ignore[no-untyped-def]
    base: dict[str, Any] = dict(
        insurer="Go Digit General Insurance Ltd",
        policy_type=policy_type,
        vehicle_class="school_bus",
        manufacture_year=2022,
        policy_start_date=date(2026, 3, 10),
        business_type="renewal",
        make="TATA",
        model="STARBUS",
        fuel="diesel",
        seating_capacity=40,
    )
    base.update(over)
    gs = GridSet(grids=tuple(grids()), aliases={"Go Digit": ("digit",)})
    return resolve(facts(**{k: v for k, v in base.items() if v is not None}), gs, Switches(), "p.pdf")


def why(r) -> str:  # type: ignore[no-untyped-def]
    return " ".join(s.decision for s in r.trace)


def rule(cell: str):  # type: ignore[no-untyped-def]
    (grid,) = grids()
    found = [r for r in grid.rules if r.od.cite.range == cell]
    assert found, cell
    return found


def test_grid_scope_and_date() -> None:
    (grid,) = grids()
    assert grid.id == "godigit/Bus Comp"
    assert grid.vehicle_classes == {"school_bus", "staff_bus"}
    assert grid.policy_types == {"comprehensive"}
    assert grid.effective_from == date(2026, 3, 1)


def test_every_citation_reads_back() -> None:
    (grid,) = grids()
    for r in grid.rules:
        assert check(BUNDLE_ROOT, r.od.cite, r.od.raw), r.od.cite
    for table in grid.mappings:
        assert isinstance(table, MappingTable)
        for row in table.rows:
            assert check(BUNDLE_ROOT, row.cite, row.raw), row.cite
            assert row.cite.sheet == MAP


def test_every_rate_cell_gives_a_rule_or_a_cited_exception() -> None:
    (grid,) = grids()
    sheet = Workbook(GODIGIT).sheet(SHEET)
    cited = {r.od.cite.range for r in grid.rules} | {e.cite.range for e in grid.exceptions}
    for first, last, cols in ((6, 31, "EFG"), (45, 58, "DEF")):
        for r in range(first, last + 1):
            for col in cols:
                coord = f"{col}{r}"
                rng = sheet.merged(coord)
                if sheet.value(rng.split(":")[0] if rng else coord) is not None:
                    assert (rng.split(":")[0] if rng else coord) in cited, coord


def test_school_bus_rate_per_operator() -> None:
    by_op = {dict(r.dims)["bus_operator"]: r.od.percent for r in rule("E9") + rule("F9") + rule("G9")}
    assert by_op == {"school": 67.5, "transporter": 57.5, "individual": 57.5}


def test_school_bus_seat_bands() -> None:
    (r,) = rule("E24")  # TN Open, 8-60 seats
    assert r.od.percent == 50 and dict(r.dims)["seating_capacity"].contains(60)
    assert not dict(r.dims)["seating_capacity"].contains(61)


def test_staff_bus_cd2_is_read_from_the_cd1_cd2_text() -> None:
    by_op = {dict(r.dims)["bus_operator"]: r.od.percent for r in rule("D54") + rule("E54") + rule("F54")}
    assert by_op == {"corporate": 52.5, "transporter": 52.5, "individual": 35}


def test_operator_not_on_the_policy_is_ambiguous() -> None:
    r = run(rto="UP01")
    assert r.status == "ambiguous" and "bus_operator" in r.trace[-1].decision, why(r)
    r = run(rto="GJ04", vehicle_class="staff_bus")
    assert r.status == "ambiguous" and "bus_operator" in r.trace[-1].decision, why(r)


def test_declined_for_every_operator_needs_no_operator() -> None:
    r = run(rto="RJ09")  # RJ Declined: "D" in every column
    assert r.status == "unsupported" and "'D'" in why(r), why(r)


def test_school_bus_under_8_seats_gets_no_school_bus_rate() -> None:
    r = run(rto="UP01", seating_capacity=7)
    assert r.status == "unsupported" and "Less Than 8 Seater" in why(r), why(r)


def test_staff_bus_up_to_10_seats_is_ambiguous() -> None:
    r = run(rto="GJ04", vehicle_class="staff_bus", seating_capacity=10)
    assert r.status == "ambiguous" and "10-seater" in why(r), why(r)


def test_staff_bus_grid_is_for_non_electric_buses() -> None:
    r = run(rto="GJ04", vehicle_class="staff_bus", fuel="electric")
    assert r.status == "unsupported" and "Non-Electric" in why(r), why(r)


def test_before_1_march_2026_is_outside_the_period() -> None:
    r = run(rto="UP01", policy_start_date=date(2026, 2, 20))
    assert r.status == "unsupported" and "2026" in r.trace[-1].decision


def test_no_satp_rates() -> None:
    assert run("satp", rto="UP01").status == "unsupported"


def test_process_notes_do_not_block_a_rate() -> None:
    (grid,) = grids()
    kinds = {
        e.kind for e in grid.exceptions if re.search(r"Discount as per system|System guidelines", e.text)
    }
    assert kinds == {"process"}
