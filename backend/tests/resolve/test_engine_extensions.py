from rater.grids.model import CitySplitTable, MappingRow, MappingTable, NotIn
from rater.resolve.engine import resolve
from rater.switches import Switches
from tests.resolve.conftest import acme, car, cite, gridset, rule

S = Switches()


def test_not_in_matches_everything_except_listed() -> None:
    others = rule(30.0, 3.0, 60, "others", zone="Zone A", fuel="petrol", cc="All")
    others = others.__class__(
        dims=(("make", NotIn(frozenset({"TATA", "KIA"}))),) + others.dims,
        od=others.od,
        tp=others.tp,
        cite=others.cite,
    )
    g = acme(rules=(others,))
    assert resolve(car(make="MARUTI"), gridset(g), S, "p.pdf").rates["od"].rate_percent == 30.0
    assert resolve(car(make="KIA"), gridset(g), S, "p.pdf").status == "unsupported"


def test_mapping_absent_source_can_be_unsupported_c8() -> None:
    seg = MappingTable(
        name="Segment",
        source="segment",
        target="tata_segment",
        rows=(MappingRow("Mini", "Mini", cite("G6")),),
        if_missing="unsupported",
        missing_reason="The workbook has no make/model → segment table and the policy prints no segment.",
    )
    g = acme(mappings=acme().mappings + (seg,))
    r = resolve(car(), gridset(g), S, "p.pdf")
    assert r.status == "unsupported" and "no make/model → segment table" in r.trace[-1].decision


def test_city_split_state_table() -> None:
    table = CitySplitTable(
        name="State → zone",
        target="zone",
        rows=(
            MappingRow("HARYANA", "Zone B", cite("P2R1", "zones")),
            MappingRow("ASSAM|*", "Zone A", cite("P1R2", "zones")),
            MappingRow("ASSAM|NAGAON", "Zone B", cite("P1R3", "zones")),
        ),
    )
    g = acme(
        mappings=(table,),
        rules=(
            rule(11.0, 1.0, 70, "A", zone="Zone A", fuel="petrol", cc="All"),
            rule(22.0, 2.0, 71, "B", zone="Zone B", fuel="petrol", cc="All"),
        ),
    )
    run = lambda **kw: resolve(car(**kw), gridset(g), S, "p.pdf")  # noqa: E731
    assert run(rto="HR26").rates["od"].rate_percent == 22.0
    assert run(rto="AS02", rto_location="NAGAON").rates["od"].rate_percent == 22.0
    assert run(rto="AS01", rto_location="GUWAHATI").rates["od"].rate_percent == 11.0  # "Rest of Assam"
    assert run(rto="AS01", rto_location=None).status == "ambiguous"  # split state needs the RTO location
    assert run(rto="KL07").status == "unsupported"  # state not in the table
    assert run(rto="XX01").status == "unsupported"  # unknown state code


def test_rto_region_table_code_then_state_fallback_with_note_and_cap() -> None:
    from rater.grids.model import RtoRegionTable
    from rater.resolve.confidence import Cap

    table = RtoRegionTable(
        name="RTO → region",
        target="zone",
        by_code=(MappingRow("ZZ01", "Zone A", cite("A2", "RTO List")),),
        by_state=(
            MappingRow(
                "KERALA",
                "Zone B",
                cite("B7"),
                note="via the RTO's state code (KL → KERALA)",
                cap=Cap("medium", "region found through the city/state reference list"),
            ),
        ),
    )
    g = acme(
        mappings=(table,),
        rules=(
            rule(11.0, 1.0, 70, "A", zone="Zone A", fuel="petrol", cc="All"),
            rule(22.0, 2.0, 71, "B", zone="Zone B", fuel="petrol", cc="All"),
        ),
    )
    direct = resolve(car(verification="text_layer", rto="ZZ01"), gridset(g), S, "p.pdf")
    assert direct.rates["od"].rate_percent == 11.0
    via_state = resolve(car(rto="KL07"), gridset(g), S, "p.pdf")
    assert via_state.rates["od"].rate_percent == 22.0
    step = next(t for t in via_state.trace if t.kind == "map")
    assert "via the RTO's state code" in step.decision
    assert "city/state reference" in via_state.confidence.reason
    assert resolve(car(rto="MH12"), gridset(g), S, "p.pdf").status == "unsupported"


def test_list_valued_fact_matches_any_keyword() -> None:
    from rater.grids.model import dim_matches

    assert dim_matches(frozenset({"tyre", "rti"}), ["Zero Depreciation", "Tyre Protect"])
    assert not dim_matches(frozenset({"tyre", "rti"}), ["Zero Depreciation"])
    assert not dim_matches(frozenset({"tyre", "rti"}), [])


def test_scoped_unclassified_term_only_blocks_policies_in_its_scope() -> None:
    from rater.grids.model import ExceptionRule

    note = ExceptionRule("unclassified", "OSN 1+ Declined", cite("H9"), when=(("zone", "Zone B"),))
    g = acme(exceptions=(note,))
    assert resolve(car(rto="ZZ01"), gridset(g), S, "p.pdf").status == "resolved"  # Zone A
    r = resolve(car(rto="ZZ02"), gridset(g), S, "p.pdf")
    assert r.status == "ambiguous" and "OSN 1+ Declined" in r.trace[-1].decision


def test_no_row_but_an_undefined_scope_covers_the_policy_is_ambiguous() -> None:
    from rater.grids.model import ExceptionRule

    undefined = ExceptionRule(
        "unclassified",
        "applies only to 'Low CD2 RTOs', which the sheet does not list",
        cite("C9"),
        when=(("zone", "Zone A"), ("fuel", "diesel")),
    )
    g = acme(exceptions=(undefined,))
    r = resolve(car(fuel="diesel"), gridset(g), S, "p.pdf")
    assert r.status == "ambiguous" and "Low CD2" in r.trace[-1].decision


def test_mapping_table_applies_only_when_its_condition_holds() -> None:
    from rater.grids.bands import Band

    light = MappingTable(
        name="RTO → cluster (LCV)",
        source="rto",
        target="zone",
        rows=(MappingRow("ZZ01", "Zone A", cite("E2", "CV RTO")),),
        when=(("gvw_t", Band(0, 7.5, True, True, "t", "upto 7.5T")),),
    )
    heavy = MappingTable(
        name="RTO → cluster (HCV)",
        source="rto",
        target="zone",
        rows=(MappingRow("ZZ01", "Zone B", cite("G2", "CV RTO")),),
        when=(("gvw_t", Band(12, float("inf"), False, True, "t", ">12T")),),
    )
    g = acme(mappings=(light, heavy))
    run = lambda **kw: resolve(car(**kw), gridset(g), S, "p.pdf")  # noqa: E731
    assert run(gvw=3500).rates["od"].rate_percent == 15.0  # Zone A, cc > 1000
    assert run(gvw=16000).rates["od"].rate_percent == 9.0  # Zone B
    assert run(gvw=None).status == "ambiguous"
    assert run(gvw=9000).status == "unsupported"  # no table for 7.5-12T in this grid
