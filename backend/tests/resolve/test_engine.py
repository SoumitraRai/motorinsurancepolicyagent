import json
from datetime import date

from hypothesis import given
from hypothesis import strategies as st

from rater.grids.model import ExceptionRule, Unpublished
from rater.resolve.confidence import Cap
from rater.resolve.engine import resolve
from rater.switches import Switches
from tests.resolve.conftest import acme, car, cite, facts, gridset, rto_map, rule

S = Switches()
POLICY = "policy.pdf"


def run(f, *grids, switches: Switches = S):  # type: ignore[no-untyped-def]
    return resolve(f, gridset(*grids), switches, POLICY)


def test_all_dims_match_resolved() -> None:
    r = run(car())
    assert r.status == "resolved"
    assert r.rates["od"].rate_percent == 15.0 and r.rates["tp"].rate_percent == 2.5
    assert r.rates["od"].grid_citation == f"{cite('E11').render()}"
    kinds = [t.kind for t in r.trace]
    assert kinds[0] == "select" and "map" in kinds and "match" in kinds and kinds[-1] == "result"
    mapping = next(t for t in r.trace if t.kind == "map")
    assert mapping.grid_citation == cite("B2", "RTO").render()
    assert mapping.policy_citation == "policy.pdf · page 1"


def test_no_row_unsupported() -> None:
    r = run(car(fuel="diesel"))
    assert r.status == "unsupported"
    assert "no row" in r.trace[-1].decision.lower()
    assert r.rates["od"].rate_percent is None


def test_two_rows_differ_ambiguous_cites_both() -> None:
    clash = acme(rules=acme().rules + (rule(13.0, 2.5, 20, "dup", zone="Zone A", fuel="petrol", cc="All"),))
    r = run(car(), clash)
    assert r.status == "ambiguous"
    final = r.trace[-1]
    assert cite("E11").render() in final.grid_citation and cite("E20").render() in final.grid_citation


def test_same_rate_from_two_rows_is_not_ambiguous() -> None:
    same = acme(rules=acme().rules + (rule(15.0, 2.5, 21, "same", zone="Zone A", fuel="petrol", cc="All"),))
    assert run(car(), same).status == "resolved"


def test_unknown_needed_fact_ambiguous() -> None:
    r = run(car(cc=None))
    assert r.status == "ambiguous"
    assert r.clarification == {"facts": ["cc"]}


def test_band_gap_ambiguous() -> None:
    r = run(car(cc=1000))  # "<1000" and ">1000" both exclude exactly 1000 (C6)
    assert r.status == "ambiguous"
    assert "band" in r.trace[-1].decision.lower()


def test_missing_mapping_unsupported() -> None:
    r = run(car(rto="ZZ99"))
    assert r.status == "unsupported"
    assert "ZZ99" in r.trace[-1].decision


def test_ambiguous_mapping_two_values() -> None:
    g = acme(mappings=(rto_map(("ZZ01", "Zone A", "B2"), ("ZZ-01", "Zone B", "B9")),))
    assert run(car(), g).status == "ambiguous"


@given(
    insurer=st.sampled_from(["Acme General Insurance Ltd", "ACME GENERAL"]),
    zone_rto=st.sampled_from(["ZZ01", "ZZ02"]),
    cc=st.integers(min_value=600, max_value=3000),
)
def test_satp_od_never_zero(insurer: str, zone_rto: str, cc: int) -> None:
    r = run(car(insurer=insurer, rto=zone_rto, cc=cc, policy_type="satp"))
    od = r.rates["od"]
    assert od.applicable is False and od.rate_percent is None and od.reason


def test_saod_tp_not_applicable() -> None:
    g = acme(policy_types=frozenset({"saod"}))
    r = run(car(policy_type="saod"), g)
    assert r.rates["tp"].applicable is False and r.rates["tp"].rate_percent is None


def test_published_zero_tp_reported() -> None:
    g = acme(rules=(rule(None, 0.0, 30, "STP zero", zone="Zone A", fuel="petrol", cc="All"),))
    r = run(car(policy_type="satp"), g)
    assert r.status == "resolved" and r.rates["tp"].rate_percent == 0.0
    assert r.rates["tp"].grid_citation == cite("F30").render()


def test_package_no_tp_rate_c3(unpublished_tp: Unpublished) -> None:
    g = acme(
        rules=(rule(20.0, None, 31, "OD only", zone="Zone A", fuel="petrol", cc="All"),),
        unpublished=(unpublished_tp,),
    )
    r = run(car(), g)
    assert r.status == "resolved"
    assert r.rates["od"].rate_percent == 20.0
    tp = r.rates["tp"]
    assert tp.applicable is True and tp.rate_percent is None
    assert tp.reason == unpublished_tp.reason and tp.grid_citation == cite("H2").render()


def test_package_missing_tp_without_statement_is_unsupported() -> None:
    g = acme(rules=(rule(20.0, None, 31, "OD only", zone="Zone A", fuel="petrol", cc="All"),))
    assert run(car(), g).status == "unsupported"


def test_footnote_overrides_cell() -> None:
    note = ExceptionRule(
        "policy_condition",
        "Payout for < 1000 CC, PO will be 5% lesser",
        cite("H3"),
        effect="reduce",
        percent=5.0,
        when=(("cc", rule(0, 0, 0, cc="<1000").dim_map["cc"]),),
        components=("od",),
    )
    g = acme(exceptions=(note,))
    small = run(car(cc=900), g)
    assert small.rates["od"].rate_percent == 7.0  # 12 - 5 points (C2 default)
    assert small.rates["tp"].rate_percent == 2.0  # TP untouched
    step = next(t for t in small.trace if t.kind == "exception")
    assert step.grid_citation == cite("H3").render()
    big = run(car(cc=1500), g)
    assert big.rates["od"].rate_percent == 15.0
    assert any(t.kind == "exception" and "does not apply" in t.decision for t in big.trace)


def test_c2_points_vs_relative() -> None:
    note = ExceptionRule(
        "policy_condition", "5% lesser", cite("H3"), effect="reduce", percent=5.0, components=("od",)
    )
    g = acme(exceptions=(note,))
    assert run(car(), g).rates["od"].rate_percent == 10.0
    rel = run(car(), g, switches=Switches(lesser_percent_means="relative"))
    assert rel.rates["od"].rate_percent == 14.25  # 15 × 0.95
    assert rel.meta["switches"]["LESSER_PERCENT_MEANS"] == "relative"


def test_decline_exception_unsupported() -> None:
    note = ExceptionRule(
        "policy_condition", "Diesel is declined", cite("H9"), effect="decline", when=(("fuel", "petrol"),)
    )
    r = run(car(), acme(exceptions=(note,)))
    assert r.status == "unsupported" and cite("H9").render() in r.trace[-1].grid_citation


def test_exception_needing_unknown_fact_is_ambiguous() -> None:
    note = ExceptionRule(
        "policy_condition",
        "Age > 10 reduced 2%",
        cite("H4"),
        effect="reduce",
        percent=2.0,
        when=(("age", rule(0, 0, 0, age=">10").dim_map["age"]),),
    )
    r = run(car(manufacture_year=None), acme(exceptions=(note,)))
    assert r.status == "ambiguous" and "manufacture_year" in r.clarification["facts"]  # type: ignore[index]


def test_broker_side_not_applied_listed() -> None:
    bonus = ExceptionRule(
        "broker_side", "Additional 2.5% CD2 for partners with 10 Lac monthly volume", cite("H5")
    )
    r = run(car(), acme(exceptions=(bonus,)))
    assert r.status == "resolved" and r.rates["od"].rate_percent == 15.0
    assert r.not_applied[0].why == "depends on broker volume, which the policy can't show"
    assert r.not_applied[0].grid_citation == cite("H5").render()


def test_d2_switch() -> None:
    bonus = ExceptionRule("broker_side", "partners with volume", cite("H5"))
    r = run(car(), acme(exceptions=(bonus,)), switches=Switches(broker_eligibility="require_evidence"))
    assert r.status == "unsupported"
    assert "broker" in r.trace[-1].decision.lower()


def test_unclassified_tc_ambiguous() -> None:
    odd = ExceptionRule("unclassified", "Kindly coordinate with RO for approvals", cite("H7"))
    r = run(car(), acme(exceptions=(odd,)))
    assert r.status == "ambiguous" and cite("H7").render() in r.trace[-1].grid_citation


def test_undefined_decline_note_ambiguous_c5() -> None:
    note = ExceptionRule(
        "undefined_decline",
        "Few RTOs for 1000-1500CC segment are declined",
        cite("F11"),
        when=(("zone", "Zone A"),),
    )
    assert run(car(), acme(exceptions=(note,))).status == "ambiguous"
    assert run(car(rto="ZZ02"), acme(exceptions=(note,))).status == "resolved"


def test_out_of_scope_and_definition_lines_do_not_block() -> None:
    lines = (
        ExceptionRule("out_of_scope", "EW Flat 20%", cite("H5")),
        ExceptionRule("definition", "Non Petrol includes Diesel", cite("H6")),
        ExceptionRule("basis", "payout on OD premium", cite("H2")),
    )
    assert run(car(), acme(exceptions=lines)).status == "resolved"


def test_d1_warn_and_strict() -> None:
    dated = acme(effective_from=date(2026, 4, 1), date_text="Effective from 1st Apr'26", date_cite=cite("A1"))
    warn = run(car(), dated)
    assert warn.status == "resolved"
    step = next(t for t in warn.trace if t.kind == "date")
    assert step.warnings and "a newer grid may exist" in step.warnings[0]
    assert warn.confidence.level == "low"  # medium (OCR) lowered one level
    strict = run(car(), dated, switches=Switches(grid_date_policy="strict"))
    assert strict.status == "unsupported"
    ended = acme(effective_from=date(2025, 1, 1), effective_to=date(2025, 12, 31), date_cite=cite("A1"))
    assert run(car(), ended).status == "unsupported"  # past a stated end date: refuse even in warn mode


def test_no_stated_date_is_a_note_without_penalty() -> None:
    r = run(car())
    assert r.status == "resolved" and r.confidence.level == "medium"
    assert any(t.kind == "date" and "not stated" in t.decision for t in r.trace)


def test_business_type_rules() -> None:
    renewal = acme(id="acme/renewal", business_types=frozenset({"renewal"}))
    rollover = acme(
        id="acme/rollover",
        business_types=frozenset({"rollover"}),
        rules=(rule(30.0, 3.0, 40, "rollover", zone="Zone A", fuel="petrol", cc="All"),),
    )
    assert run(car(business_type="rollover"), renewal, rollover).rates["od"].rate_percent == 30.0
    unknown = run(car(business_type=None), renewal, rollover)
    assert unknown.status == "ambiguous" and "business_type" in unknown.clarification["facts"]  # type: ignore[index]
    # A grid that doesn't split on business type is not blocked by an unknown business type (A3).
    assert run(car(business_type=None)).status == "resolved"


def test_resolve_deterministic_bytes() -> None:
    assert run(car()).to_json() == run(car()).to_json()


def test_select_insurer_aliases() -> None:
    assert run(car(insurer="ACME GENERAL INSURANCE COMPANY LIMITED")).status == "resolved"
    other = run(car(insurer="Unheard Of Insurance"))
    assert other.status == "unsupported" and "Acme" in other.trace[-1].decision
    known_no_grid = run(car(insurer="Zenith Insurance"))
    assert known_no_grid.status == "unsupported"


def test_unknown_vehicle_class_or_policy_type_is_ambiguous() -> None:
    assert run(car(vehicle_class=None)).status == "ambiguous"
    assert run(car(policy_type=None)).status == "ambiguous"


def test_vehicle_class_without_grid_is_unsupported() -> None:
    r = run(car(vehicle_class="two_wheeler"))
    assert r.status == "unsupported" and "two_wheeler" in r.trace[-1].decision


def test_max_cd2_labelled_c7() -> None:
    g = acme(rules=(rule(None, 29.5, 50, "cluster", zone="Zone A", fuel="petrol", cc="All"),))
    labelled = g.rules[0].__class__(
        dims=g.rules[0].dims,
        od=None,
        tp=g.rules[0].tp.__class__(29.5, 0.295, cite("E50"), label="Max CD2"),  # type: ignore[union-attr]
        cite=g.rules[0].cite,
    )
    r = run(car(policy_type="satp"), acme(rules=(labelled,)))
    assert "insurer's published maximum (Max CD2)" in r.rates["tp"].reason
    assert r.rates["tp"].raw_cell_value == "0.295"


def test_grid_mapping_beats_printed_location() -> None:
    r = run(car(rto="ZZ02", rto_location="Zone A town"))
    assert r.rates["od"].rate_percent == 9.0  # grid's own RTO → zone table decides


def test_caps_and_weakest_link_in_result() -> None:
    capped = acme(caps=(Cap("low", "slab footnote assumption (C1)"),))
    r = run(car(), capped)
    assert r.confidence.level == "low" and "C1" in r.confidence.reason
    text_layer = run(
        facts(verification="text_layer", **{k: v.value for k, v in car() if v.value is not None})
    )
    assert text_layer.confidence.level == "high"


def test_result_json_is_valid_and_keeps_example_keys() -> None:
    body = json.loads(run(car()).to_json())
    assert {"status", "facts", "rates", "trace", "confidence"} <= set(body)
    assert {"decision", "policyCitation", "gridCitation"} <= set(body["trace"][0])
