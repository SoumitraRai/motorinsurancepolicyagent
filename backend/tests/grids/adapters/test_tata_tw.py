from datetime import date

from openpyxl.utils import get_column_letter

from rater.bundle import BUNDLE_ROOT
from rater.grids.adapters.tata_cv_tw import load_tw
from rater.grids.readback import check
from rater.grids.xlsx import Workbook

TATA = next((BUNDLE_ROOT / "raters/tata-aig").rglob("*.xlsx"))


_GRID = None


def grid():  # type: ignore[no-untyped-def]
    global _GRID
    if _GRID is None:
        _GRID = load_tw(BUNDLE_ROOT)
    return _GRID


def test_scope_and_date() -> None:
    g = grid()
    assert g.insurer == "Tata AIG" and g.vehicle_classes == {"two_wheeler", "scooter", "motorcycle", "moped"}
    assert g.policy_types == {"comprehensive", "saod", "satp"} and g.effective_from == date(2025, 11, 1)


def test_rule_counts_match_sheet() -> None:
    sheet = Workbook(TATA).sheet("TW")
    clusters = [c for c in range(5, sheet.max_column + 1) if sheet.value(f"{get_column_letter(c)}5")]
    expected = 0
    for r in range(6, sheet.max_row + 1):
        if not sheet.value(f"B{r}"):
            continue
        per = 2 if str(sheet.value(f"D{r}")).strip().lower() == "all" else 1
        expected += per * sum(
            1 for c in clusters if isinstance(sheet.value(f"{get_column_letter(c)}{r}"), int | float)
        )
    assert len(grid().rules) == expected


def test_all_type_splits_into_od_and_tp_rules() -> None:
    for rule in grid().rules:
        pt = dict(rule.dims)["policy_type"]
        if pt == "satp":
            assert rule.tp is not None and rule.od is None
        else:
            assert rule.od is not None and rule.tp is None


def test_every_citation_reads_back_sampled() -> None:
    g = grid()
    for rule in g.rules[::11]:
        cell = rule.od or rule.tp
        assert cell is not None and check(BUNDLE_ROOT, cell.cite, cell.raw), cell.cite.render()
    for row in g.mappings[0].rows:  # type: ignore[union-attr]
        assert check(BUNDLE_ROOT, row.cite, row.raw)
    for e in g.exceptions:
        assert check(BUNDLE_ROOT, e.cite, e.text), e.cite.render()
    assert "unclassified" not in {e.kind for e in g.exceptions}
