"""Synthetic policies through the real grids and engine, one per two-wheeler grid (plan T14).

Each case picks an RTO from the grid's own map whose cluster has a matching row in the file, so the test
checks wiring end to end (selection → mapping → matching → citation) without any sample policy (NN5).
"""

from datetime import date
from typing import Any

import pytest

from rater.bundle import BUNDLE_ROOT
from rater.facts import Fact, Facts
from rater.grids.model import RtoRegionTable, dim_matches
from rater.grids.readback import check
from rater.grids.registry import load_all
from rater.resolve.engine import resolve
from rater.switches import Switches

_GS = None


def gs():  # type: ignore[no-untyped-def]
    global _GS
    if _GS is None:
        _GS = load_all(BUNDLE_ROOT)
    return _GS


def facts(**values: Any) -> Facts:
    f = Facts()
    for k, v in values.items():
        setattr(f, k, Fact(value=v, page=1, quote=f"{k} {v}", verification="verified_both"))
    return f


def rto_for(grid_id: str, want: dict[str, Any], component: str) -> tuple[str, str | None]:
    """An RTO code (and RTO location) whose mapped cluster/region has a row matching `want`."""
    grid = next(g for g in gs().grids if g.id == grid_id)
    table = grid.mappings[0]
    rows = table.by_code if isinstance(table, RtoRegionTable) else table.rows
    for row in rows:
        for rule in grid.rules:
            dims = dict(rule.dims)
            if getattr(rule, component) is None or dims.get(table.target) != row.value:
                continue
            if all(
                dim_matches(w, want[d]) for d, w in rule.dims if d not in (table.target,) and d in want
            ) and all(d in want or d == table.target for d, _ in rule.dims):
                return row.key, row.value
    pytest.skip(f"no RTO in {grid_id} has a row for {want}")


CASES = [
    (
        "godigit/TW SATP",
        "Go Digit General Insurance Ltd",
        "tp",
        dict(
            vehicle_class="scooter",
            tw_type="scooter",
            policy_type="satp",
            fuel="petrol",
            cc=110,
            make="HONDA",
        ),
    ),
    (
        "reliance/tw-scooter",
        "Reliance General Insurance",
        "od",
        dict(
            vehicle_class="scooter",
            tw_type="scooter",
            policy_type="comprehensive",
            business_type="renewal",
            fuel="petrol",
            cc=110,
            make="HONDA",
        ),
    ),
    (
        "tata-aig/TW",
        "TATA AIG General Insurance",
        "tp",
        dict(
            vehicle_class="moped",
            tw_type="moped",
            policy_type="satp",
            business_type="renewal",
            fuel="petrol",
            cc=100,
            make="TVS",
        ),
    ),
]


@pytest.mark.parametrize(("grid_id", "insurer", "component", "want"), CASES, ids=[c[0] for c in CASES])
def test_two_wheeler_resolves_through_real_grid(
    grid_id: str, insurer: str, component: str, want: dict
) -> None:  # type: ignore[type-arg]
    code, value = rto_for(grid_id, {**want, "policy_type": want["policy_type"]}, component)
    f_values = {k: v for k, v in want.items() if k != "tw_type"}
    location = value if grid_id.startswith("tata") else None
    f = facts(
        insurer=insurer,
        rto=code,
        policy_start_date=date(2026, 3, 1),
        **f_values,
        **({"rto_location": location} if location else {}),
    )
    r = resolve(f, gs(), Switches(), "synthetic.pdf")
    assert r.status == "resolved", [t.decision for t in r.trace]
    rate = r.rates[component]
    (c,) = rate.citations
    from rater.citations import XlsxCite

    assert check(BUNDLE_ROOT, XlsxCite(c["file"], c["sheet"], c["range"]), rate.raw_cell_value)
    other = "od" if component == "tp" else "tp"
    if want["policy_type"] == "satp":
        assert r.rates[other].applicable is False and r.rates[other].rate_percent is None
