from rater.bundle import BUNDLE_ROOT
from rater.grids.adapters.godigit_tw import CODES, load
from rater.grids.model import MappingTable
from rater.grids.readback import check
from rater.grids.twsegments import parse_tw_segment
from rater.grids.xlsx import Workbook

GODIGIT = next((BUNDLE_ROOT / "raters/godigit").rglob("*.xlsx"))
_GRIDS = None


def grids():  # type: ignore[no-untyped-def]
    global _GRIDS
    if _GRIDS is None:
        _GRIDS = {g.id: g for g in load(BUNDLE_ROOT)}
    return _GRIDS


def test_grids_and_scope() -> None:
    g = grids()
    assert set(g) == {
        "godigit/TW 1+1",
        "godigit/TW SATP",
        "godigit/TW 1+5",
        "godigit/2W Grid 5+5",
        "godigit/TW SAOD",
    }
    for grid in g.values():
        assert grid.vehicle_classes == {"two_wheeler", "scooter", "motorcycle"}
    assert g["godigit/TW SATP"].policy_types == {"satp"}
    assert g["godigit/TW 1+5"].business_types == {"new"} and g["godigit/2W Grid 5+5"].business_types == {
        "new"
    }
    assert g["godigit/TW SAOD"].policy_types == {"saod"}


def _expected(sheet_name: str, seg_col: str, rate_cols: str, start: int) -> int:
    sheet = Workbook(GODIGIT).sheet(sheet_name)
    total = 0
    for r in range(start, sheet.max_row + 1):
        if not sheet.value(f"B{r}") or not sheet.value(f"{seg_col}{r}"):
            continue
        labels = [
            str(sheet.value(f"{seg_col}{x}"))
            for x in range(start, sheet.max_row + 1)
            if sheet.value(f"B{x}") == sheet.value(f"B{r}") and sheet.value(f"{seg_col}{x}")
        ]
        alts = len(parse_tw_segment(str(sheet.value(f"{seg_col}{r}")), labels))
        numeric = sum(1 for c in rate_cols if isinstance(sheet.value(f"{c}{r}"), int | float))
        total += alts * numeric
    return total


def test_rule_counts_track_numeric_cells() -> None:
    g = grids()
    assert len(g["godigit/TW SATP"].rules) == _expected("TW 1+1 & SATP", "C", "F", 5)
    one = g["godigit/TW 1+1"].rules
    assert len(one) == _expected("TW 1+1 & SATP", "C", "E", 5)


def test_every_citation_reads_back() -> None:
    for grid in grids().values():
        for rule in grid.rules[::7]:
            for cell in (rule.od, rule.tp):
                if cell is not None:
                    assert check(BUNDLE_ROOT, cell.cite, cell.raw), cell.cite.render()
        for e in grid.exceptions[::5]:
            assert (
                check(BUNDLE_ROOT, e.cite, e.raw if hasattr(e, "raw") else e.text)
                or e.kind == "policy_condition"
            )
        for table in grid.mappings:
            assert isinstance(table, MappingTable)
            for row in table.rows[::50]:
                assert check(BUNDLE_ROOT, row.cite, row.raw), row.cite.render()


def test_text_codes_become_no_rate_exceptions() -> None:
    nb = grids()["godigit/TW 1+5"]
    codes = [e for e in nb.exceptions if e.effect == "decline" and any(c in e.text for c in CODES)]
    assert codes and all(e.when for e in codes)


def test_reductions_and_format_errors_scoped_to_rows() -> None:
    g = grids()["godigit/2W Grid 5+5"]
    reductions = [e for e in g.exceptions if e.effect == "reduce"]
    assert reductions and {d for e in reductions for d, _ in e.when} & {"has_add_ons", "cpa_cover"}
    assert all(e.percent and e.percent > 0 for e in reductions)
    assert any(e.kind == "unclassified" and "Format error" in e.text for e in g.exceptions)


def test_rto_tables_use_the_right_column() -> None:
    names = {g.id: g.mappings[0].name for g in grids().values()}
    assert "1+1" in names["godigit/TW 1+1"] and "1+5" in names["godigit/TW 1+5"]
    assert "SAOD" in names["godigit/TW SAOD"]
