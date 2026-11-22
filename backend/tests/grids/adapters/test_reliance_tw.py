from datetime import date

from rater.bundle import BUNDLE_ROOT
from rater.grids.adapters.reliance_tw import load
from rater.grids.model import MappingTable, RtoRegionTable
from rater.grids.readback import check
from rater.grids.xlsx import Workbook

RELIANCE = next((BUNDLE_ROOT / "raters/reliance-indusind").rglob("*.xlsx"))


def grid():  # type: ignore[no-untyped-def]
    (g,) = load(BUNDLE_ROOT)
    return g


def test_scope() -> None:
    g = grid()
    assert g.insurer == "Reliance" and g.vehicle_classes == {"two_wheeler", "scooter", "motorcycle"}
    assert g.policy_types == {"comprehensive", "saod", "satp"} and g.effective_from == date(2026, 1, 1)


def test_rule_counts_match_numeric_cells() -> None:
    sheet = Workbook(RELIANCE).sheet("TW SCOOTER GRID")
    cells = sum(
        1
        for r in range(3, sheet.max_row + 1)
        if sheet.value(f"B{r}")
        for c in "CDEFG"
        if isinstance(sheet.value(f"{c}{r}"), int | float)
    )
    assert len(grid().rules) == cells


def test_motorcycles_only_in_saod_column() -> None:
    for rule in grid().rules:
        dims = dict(rule.dims)
        if dims["policy_type"] == "saod":
            assert "tw_type" not in dims
        else:
            assert dims["tw_type"] == "scooter"


def test_every_citation_reads_back() -> None:
    g = grid()
    for rule in g.rules:
        cell = rule.od or rule.tp
        assert cell is not None and check(BUNDLE_ROOT, cell.cite, cell.raw), cell.cite.render()
    for e in g.exceptions:
        assert check(BUNDLE_ROOT, e.cite, e.text), e.cite.render()


def test_tc_lines_and_scope() -> None:
    g = grid()
    assert "unclassified" not in {e.kind for e in g.exceptions}
    ev = next(e for e in g.exceptions if "EV Makes" in e.text)
    assert (ev.effect, ev.percent) == ("flat", 25.0) and ("fuel", "electric") in ev.when
    regions = [e for e in g.exceptions if "RTO regions" in e.text]
    assert len(regions) == 2 and all(any(d == "reliance_city" for d, _ in e.when) for e in regions)
    assert any(e.kind == "broker_side" and "Contest" in e.text for e in g.exceptions)


def test_region_and_city_tables() -> None:
    g = grid()
    region = next(m for m in g.mappings if isinstance(m, RtoRegionTable))
    city = next(m for m in g.mappings if isinstance(m, MappingTable))
    assert city.optional and city.target == "reliance_city"
    assert {r.value for r in region.by_code} <= {dict(r.dims)["region"] for r in g.rules} | {
        r.value for r in region.by_code if "RTO List" in r.value
    }
