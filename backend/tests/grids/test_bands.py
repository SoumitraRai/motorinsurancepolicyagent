import pytest

from rater.grids.bands import parse_band


@pytest.mark.parametrize(
    ("label", "unit", "inside", "outside"),
    [
        ("<1000", "cc", [999, 1], [1000, 1001]),
        (">1000", "cc", [1001, 5000], [1000, 999]),
        ("1000-1500", "cc", [1000, 1500, 1200], [999, 1501]),
        (">1500", "cc", [1501], [1500]),
        ("<1000CC", "cc", [999], [1000]),
        ("1000 CC-1500 CC", "cc", [1000, 1500], [1501]),
        (">1500 CC", "cc", [1501], [1500]),
        ("<10k", "inr", [9999], [10000]),
        (">10-50k", "inr", [10001, 50000], [10000, 50001]),
        (">50k-1L", "inr", [50001, 100000], [50000, 100001]),
        (">1L-2L", "inr", [100001, 200000], [100000, 200001]),
        (">2L", "inr", [200001], [200000]),
        ("<10", "years", [9], [10]),
        (">10", "years", [11], [10]),
        ("Upto 5years", "years", [0, 5], [6]),
        ("Above 5 Years", "years", [6], [5]),
        ("0-5 years", "years", [0, 5], [6]),
    ],
)
def test_parse_band(label: str, unit: str, inside: list[float], outside: list[float]) -> None:
    band = parse_band(label, unit)
    assert band is not None, label
    assert band.label == label and band.unit == unit
    for x in inside:
        assert band.contains(x), (label, x)
    for x in outside:
        assert not band.contains(x), (label, x)


def test_all_is_unbounded() -> None:
    band = parse_band("All", "years")
    assert band is not None and band.contains(0) and band.contains(10**9)


def test_unparseable_is_none() -> None:
    assert parse_band("Petrol", "cc") is None
    assert parse_band("", "cc") is None


def test_band_gap_values() -> None:
    # Adjacent published bands leave their shared boundary uncovered (spec C6): no band may claim it.
    pairs = [("<1000", ">1000", "cc", 1000), ("<10", ">10", "years", 10), ("<10k", ">10-50k", "inr", 10000)]
    for low, high, unit, edge in pairs:
        a, b = parse_band(low, unit), parse_band(high, unit)
        assert a is not None and b is not None
        assert not a.contains(edge) and not b.contains(edge)
