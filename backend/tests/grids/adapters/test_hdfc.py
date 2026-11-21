import re
from datetime import date

from rater.bundle import BUNDLE_ROOT
from rater.citations import PdfGridCite
from rater.grids.adapters.hdfc_pvtcar_pdf import load
from rater.grids.model import CitySplitTable
from rater.grids.pdfgrid import pdf_lines
from rater.grids.readback import check

HDFC = next((BUNDLE_ROOT / "raters/hdfc-ergo").rglob("*.pdf"))
PCT = re.compile(r"^\d+(\.\d+)?%$")


def test_hdfc_loads_with_dates_scope_and_caps() -> None:
    (grid,) = load(BUNDLE_ROOT)
    assert grid.insurer == "HDFC ERGO" and grid.vehicle_classes == {"private_car"}
    assert grid.policy_types == {"comprehensive", "saod"}
    assert grid.effective_from == date(2025, 2, 1) and grid.effective_to is None
    assert grid.caps and "C1" in grid.caps[0].reason
    assert grid.new_business_counts_as_ncb
    assert any(u.policy_type == "comprehensive" and u.component == "tp" for u in grid.unpublished)


def test_rule_counts_match_pdf_rows() -> None:
    (grid,) = load(BUNDLE_ROOT)
    rate_cells = sum(
        len(ln.words) - 1
        for ln in pdf_lines(HDFC)
        if len(ln.words) > 1 and all(PCT.match(w.text) for w in ln.words[1:])
    )
    assert len(grid.rules) == rate_cells  # one rule per published percentage cell


def test_every_rule_citation_reads_back() -> None:
    (grid,) = load(BUNDLE_ROOT)
    for rule in grid.rules:
        assert rule.od is not None and isinstance(rule.od.cite, PdfGridCite)
        assert check(BUNDLE_ROOT, rule.od.cite, rule.od.raw), rule.od.cite.render()
    (table,) = [m for m in grid.mappings if isinstance(m, CitySplitTable)]
    for row in table.rows:
        assert check(BUNDLE_ROOT, row.cite, row.raw), row.cite.render()


def test_fuel_groups_come_from_footnotes() -> None:
    (grid,) = load(BUNDLE_ROOT)
    fuels = {frozenset(v) for r in grid.rules for d, v in r.dims if d == "fuel"}
    assert frozenset({"petrol", "electric", "hybrid"}) in fuels
    assert frozenset({"diesel", "cng", "lpg"}) in fuels


def test_state_table_has_splits_and_whole_states() -> None:
    (grid,) = load(BUNDLE_ROOT)
    (table,) = [m for m in grid.mappings if isinstance(m, CitySplitTable)]
    keys = {r.key for r in table.rows}
    assert "ASSAM|*" in keys and "ASSAM|NAGAON" in keys and "KARNATAKA|BANGALORE" in keys
    assert "DELHI" in keys and "HARYANA" in keys
    assert {r.value for r in table.rows} == {"Zone 1", "Zone 2"}
