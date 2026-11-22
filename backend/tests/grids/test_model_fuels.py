from rater.grids.model_fuels import ALLOWED, entries, fuels_for


def test_reference_list_rows_are_valid() -> None:
    rows = entries()
    assert len(rows) > 300
    keys = [(r.make, r.model) for r in rows]
    assert len(keys) == len(set(keys))  # one row per make + model
    for r in rows:
        assert r.fuels and r.fuels <= ALLOWED and r.make == r.make.upper() and r.source


def test_longest_listed_model_wins() -> None:
    assert fuels_for("MAHINDRA", "BOLERO NEO N10") == frozenset({"diesel"})
    assert fuels_for("MAHINDRA", "BOLERO B6") == frozenset({"diesel", "petrol"})
    assert fuels_for("HYUNDAI", "CRETA N LINE") == frozenset({"petrol"})
    assert fuels_for("HYUNDAI", "CRETA SX") == frozenset({"petrol", "diesel", "electric"})


def test_make_must_match() -> None:
    assert fuels_for("TATA", "JIMNY") is None
