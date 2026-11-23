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


def test_confirmed_by_both_engines_is_high() -> None:
    # PO 2026-11-23 (C4 amended): both OCR engines gave the same value independently.
    assert fact_level(f("confirmed_both")) == "high"


def mix(confirmed: int, other: str, n_other: int) -> dict[str, Fact]:
    out = {f"a{i}": f("confirmed_both") for i in range(confirmed)}
    out.update({f"z{i}": f(other) for i in range(n_other)})
    return out


def test_ninety_percent_confirmed_is_high() -> None:
    c = overall(mix(9, "verified_one", 1), warnings=0)
    assert c.level == "high"
    assert "9 of 10" in c.reason and "90%" in c.reason


def test_seventy_percent_confirmed_is_medium_and_below_is_low() -> None:
    assert overall(mix(7, "verified_one", 3), warnings=0).level == "medium"
    assert overall(mix(6, "verified_one", 4), warnings=0).level == "low"


def test_never_below_the_weakest_link() -> None:
    # Every fact in both engines' text, values not cross-checked: medium, as before.
    assert overall(mix(0, "verified_both", 4), warnings=0).level == "medium"


def test_row_fact_read_by_one_engine_is_low() -> None:
    facts = mix(9, "verified_one", 0) | {"cc": f("verified_one", page=2)}
    c = overall(facts, warnings=0, row={"cc"})
    assert c.level == "low"
    assert "cc" in c.reason and "page 2" in c.reason
    assert overall(facts, warnings=0, row={"a0"}).level == "high"  # cc only helped pick the grid


def test_unknown_row_fact_is_low() -> None:
    facts = mix(9, "verified_one", 0) | {"cc": Fact(verification="not_found")}
    assert overall(facts, warnings=0, row={"cc"}).level == "low"


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
