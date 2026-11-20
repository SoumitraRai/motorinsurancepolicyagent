from rater.facts import Fact
from rater.resolve.confidence import Cap, fact_level, overall


def f(verification: str, page: int | None = 1) -> Fact:
    return Fact(value="x", page=page, quote="q", verification=verification)


def test_text_layer_high_ocr_medium_one_engine_low() -> None:
    assert fact_level(f("text_layer")) == "high"
    assert fact_level(f("verified_both")) == "medium"
    assert fact_level(f("verified_one")) == "low"
    assert fact_level(f("unverified")) == "low"
    assert fact_level(Fact(verification="not_found")) == "unknown"
    assert fact_level(f("reviewer_supplied")) == "medium"


def test_confidence_weakest_link() -> None:
    c = overall(
        {"rto": f("text_layer"), "cc": f("verified_one", page=2), "fuel": f("verified_both")}, warnings=0
    )
    assert c.level == "low"
    assert "cc" in c.reason and "page 2" in c.reason


def test_d1_warning_lowers_one_level() -> None:
    facts = {"rto": f("text_layer")}
    assert overall(facts, warnings=0).level == "high"
    assert overall(facts, warnings=1).level == "medium"
    assert overall(facts, warnings=5).level == "low"  # never below low on warnings alone


def test_caps_apply_and_are_named() -> None:
    c = overall({"rto": f("text_layer")}, warnings=0, caps=[Cap("medium", "slab footnote assumption (C1)")])
    assert c.level == "medium" and c.capped_by == ["slab footnote assumption (C1)"]


def test_no_used_facts_is_low() -> None:
    assert overall({}, warnings=0).level == "low"
