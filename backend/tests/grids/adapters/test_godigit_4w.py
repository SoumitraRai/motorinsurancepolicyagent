from rater.bundle import BUNDLE_ROOT
from rater.grids.adapters.godigit_4w import load
from rater.grids.makes import canonical_make
from rater.grids.model import MappingTable, NotIn
from rater.grids.readback import check
from rater.grids.xlsx import Workbook

GODIGIT = next((BUNDLE_ROOT / "raters/godigit").rglob("*.xlsx"))


def grids():  # type: ignore[no-untyped-def]
    return {g.id: g for g in load(BUNDLE_ROOT)}


def test_loads_satp_and_new_business() -> None:
    g = grids()
    satp, nb = g["godigit/4W SATP"], g["godigit/4W New Business 1+3"]
    assert satp.policy_types == {"satp"} and satp.business_types is None
    assert nb.policy_types == {"comprehensive"} and nb.business_types == {"new"}
    assert all(r.tp is not None and r.tp.label == "Max CD2" for r in satp.rules)


def test_rule_counts_match_sheet_rows() -> None:
    sheet = Workbook(GODIGIT).sheet("4W SATP")
    expected = 0
    for r in range(3, sheet.max_row + 1):
        cluster = sheet.value(f"B{r}")
        if cluster:
            expected += len(str(cluster).split("/"))
    assert len(grids()["godigit/4W SATP"].rules) == expected


def test_every_rule_citation_reads_back() -> None:
    for grid in grids().values():
        for rule in grid.rules:
            for cell in (rule.od, rule.tp):
                if cell is not None:
                    assert check(BUNDLE_ROOT, cell.cite, cell.raw), cell.cite.render()
        for table in grid.mappings:
            assert isinstance(table, MappingTable)
            for row in table.rows[:200]:
                assert check(BUNDLE_ROOT, row.cite, row.raw), row.cite.render()
        for e in grid.exceptions:
            assert check(BUNDLE_ROOT, e.cite, e.text), e.cite.render()


def test_fraction_values_become_percent() -> None:
    rule = grids()["godigit/4W SATP"].rules[0]
    assert rule.tp is not None and abs(rule.tp.percent - float(rule.tp.raw) * 100) < 1e-9


def test_decline_cluster_rows_also_become_decline_exceptions() -> None:
    satp = grids()["godigit/4W SATP"]
    assert any(e.effect == "decline" and ("cluster", "All_India_Decline") in e.when for e in satp.exceptions)


def test_row_notes_scoped_to_their_row() -> None:
    satp = grids()["godigit/4W SATP"]
    kinds = {e.kind for e in satp.exceptions}
    assert "undefined_decline" in kinds and "policy_condition" in kinds
    for e in satp.exceptions:
        assert any(d == "cluster" for d, _ in e.when)


def test_renault_listed_twice_and_others_rule() -> None:
    nb = grids()["godigit/4W New Business 1+3"]
    renault = [
        r
        for r in nb.rules
        if (w := dict(r.dims).get("make")) is not None and isinstance(w, frozenset) and "RENAULT" in w
    ]
    assert len({r.od.cite.range[0] for r in renault if r.od}) == 2  # columns G and H (A2 → ambiguous)
    assert any(isinstance(dict(r.dims).get("make"), NotIn) for r in nb.rules)
    assert {dict(r.dims)["od_term_years"] for r in nb.rules} == {"1", "3"}


def test_make_aliases() -> None:
    assert canonical_make("Volks") == canonical_make("VOLKSWAGEN") == "VOLKSWAGEN"
    assert canonical_make("Citrone") == "CITROEN"
    assert canonical_make("MARUTI SUZUKI") == canonical_make("Maruti") == "MARUTI"
    assert canonical_make("Hyundai") == "HYUNDAI"
