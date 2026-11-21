from datetime import date

from rater.bundle import BUNDLE_ROOT
from rater.grids.adapters.reliance_pvtcar import load
from rater.grids.model import RtoRegionTable
from rater.grids.readback import check
from rater.grids.xlsx import Workbook

RELIANCE = next((BUNDLE_ROOT / "raters/reliance-indusind").rglob("*.xlsx"))


def grid():  # type: ignore[no-untyped-def]
    (g,) = load(BUNDLE_ROOT)
    return g


def table(g) -> RtoRegionTable:  # type: ignore[no-untyped-def]
    (t,) = [m for m in g.mappings if isinstance(m, RtoRegionTable)]
    return t


def test_scope_dates_and_business() -> None:
    g = grid()
    assert g.insurer == "Reliance" and g.vehicle_classes == {"private_car"}
    assert g.policy_types == {"comprehensive", "saod", "satp"}
    assert g.business_types == {"renewal", "rollover"}  # "Old Business" grid
    assert g.effective_from == date(2026, 1, 1)
    assert any(u.policy_type == "comprehensive" and u.component == "tp" for u in g.unpublished)


def test_rule_counts_match_sheet_rows() -> None:
    sheet = Workbook(RELIANCE).sheet("PRIVATE CAR COMP, SAOD & STP")
    rows = [r for r in range(3, sheet.max_row + 1) if sheet.value(f"B{r}")]
    assert len(grid().rules) == 4 * len(rows)  # petrol/bifuel comp, diesel/EV comp, SAOD, STP per row


def test_every_citation_reads_back() -> None:
    g = grid()
    for rule in g.rules:
        for cell in (rule.od, rule.tp):
            if cell is not None:
                assert check(BUNDLE_ROOT, cell.cite, cell.raw), cell.cite.render()
    for row in table(g).by_code:
        assert check(BUNDLE_ROOT, row.cite, row.raw), row.cite.render()
    for e in g.exceptions:
        assert check(BUNDLE_ROOT, e.cite, e.text), e.cite.render()


def test_every_rto_list_row_is_resolved_or_explained() -> None:
    g = grid()
    sheet = Workbook(RELIANCE).sheet("RTO List")
    codes = {str(sheet.value(f"A{r}")) for r in range(2, sheet.max_row + 1) if sheet.value(f"A{r}")}
    mapped = {r.key for r in table(g).by_code}
    assert mapped <= codes
    assert len(mapped) / len(codes) > 0.9  # the rest are regions no grid row covers (e.g. Ladakh)


def test_city_named_regions_resolve_through_the_city_state_list_with_a_cap() -> None:
    g = grid()
    via_city = [r for r in table(g).by_code if "city → state" in r.note]
    assert via_city and all(r.cap is not None for r in via_city)
    assert {r.value for r in via_city} <= {
        rule_region for rule in g.rules for d, rule_region in rule.dims if d == "region"
    }


def test_zone_conflicts_give_two_values() -> None:
    t = table(grid())
    by_key: dict[str, set[str]] = {}
    for r in t.by_code:
        by_key.setdefault(r.key, set()).add(r.value)
    conflicted = [k for k, v in by_key.items() if len(v) > 1]
    assert conflicted  # RTO List zone disagrees with the grid row's zone somewhere (A2 → ambiguous)
    for k in conflicted:
        assert any("RTO List" in v for v in by_key[k])


def test_state_fallback_rows_exist_for_covered_states() -> None:
    states = {r.key for r in table(grid()).by_state}
    assert {"TAMIL NADU", "KERALA", "MAHARASHTRA", "UTTAR PRADESH", "ASSAM"} <= states


def test_tc_lines_scoped_to_od() -> None:
    g = grid()
    kinds = {e.kind for e in g.exceptions}
    assert {"basis", "policy_condition", "out_of_scope", "broker_side", "post_issue"} <= kinds
    assert "unclassified" not in kinds
    cc_rule = next(e for e in g.exceptions if "1000 CC" in e.text)
    assert cc_rule.effect == "reduce" and cc_rule.components == ("od",) and cc_rule.when[0][0] == "cc"
    cpa = next(e for e in g.exceptions if "CPA" in e.text)
    assert cpa.when == (("cpa_cover", "no"),)
