from datetime import date

from openpyxl.utils import get_column_letter

from rater.bundle import BUNDLE_ROOT
from rater.grids.adapters.tata_pvtcar import load
from rater.grids.model import MappingTable
from rater.grids.readback import check
from rater.grids.xlsx import Workbook

TATA = next((BUNDLE_ROOT / "raters/tata-aig").rglob("*.xlsx"))
_GRID = None


def grid():  # type: ignore[no-untyped-def]
    global _GRID
    if _GRID is None:
        (_GRID,) = load(BUNDLE_ROOT)
    return _GRID


def test_scope_and_dates() -> None:
    g = grid()
    assert g.insurer == "Tata AIG" and g.policy_types == {"comprehensive", "saod", "satp"}
    assert g.effective_from == date(2025, 11, 1)
    assert g.business_types is None  # business type is a row dimension here
    assert any(u.policy_type == "comprehensive" and u.component == "tp" for u in g.unpublished)


def test_rule_counts_match_sheet() -> None:
    sheet = Workbook(TATA).sheet("Pvtcar")
    data_rows = [
        r for r in range(6, sheet.max_row + 1) if sheet.value(f"G{r}") and not sheet.is_aggregate(f"M{r}")
    ]
    clusters = [
        c
        for c in range(13, sheet.max_column + 1)
        if sheet.value(f"{get_column_letter(c)}5") and get_column_letter(c) <= "BO"
    ]
    assert len(grid().rules) == len(data_rows) * len(clusters)


def test_every_citation_reads_back_sampled() -> None:
    g = grid()
    for rule in g.rules[::97]:  # every 97th of ~30k cells, deterministic
        cell = rule.od or rule.tp
        assert cell is not None and check(BUNDLE_ROOT, cell.cite, cell.raw), cell.cite.render()
    for table in g.mappings:
        assert isinstance(table, MappingTable)
        for row in table.rows:
            assert check(BUNDLE_ROOT, row.cite, row.raw), row.cite.render()
    for e in g.exceptions:
        assert check(BUNDLE_ROOT, e.cite, e.text), e.cite.render()


def test_satp_rows_give_tp_and_package_rows_give_od() -> None:
    for rule in grid().rules:
        pt = dict(rule.dims)["policy_type"]
        assert (rule.tp is not None) == (pt == "satp") and (rule.od is not None) == (pt != "satp")


def test_segment_mapping_refuses_when_policy_prints_none_c8() -> None:
    seg = next(m for m in grid().mappings if isinstance(m, MappingTable) and m.source == "segment")
    assert seg.if_missing == "unsupported" and "no make/model" in seg.missing_reason


def test_no_unclassified_guideline_lines() -> None:
    assert "unclassified" not in {e.kind for e in grid().exceptions}
