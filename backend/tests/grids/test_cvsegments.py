import pytest

from rater.grids.cvsegments import CvSegment, parse_cv_segment
from rater.grids.model import dim_matches


def ok(label: str, **facts) -> bool:  # type: ignore[no-untyped-def]
    seg = parse_cv_segment(label)
    assert isinstance(seg, CvSegment) and not seg.undefined, seg
    return all(d in facts and dim_matches(w, facts[d]) for d, w in seg.dims)


def test_gcv4_tonnage_and_age() -> None:
    assert ok("GCV4 upto 1.6T 0-5 years", vehicle_class="gcv", gvw_t=1.5, age=3)
    assert not ok("GCV4 upto 1.6T 0-5 years", vehicle_class="gcv", gvw_t=1.7, age=3)
    assert not ok("GCV4 upto 1.6T 0-5 years", vehicle_class="gcv", gvw_t=1.5, age=6)
    assert ok("GCV4 1.6T-2.5T 3+ years", vehicle_class="gcv", gvw_t=2.0, age=4)
    assert not ok(
        "GCV4 1.6T-2.5T 3+ years", vehicle_class="gcv", gvw_t=1.6, age=4
    )  # 1.6 belongs to "upto 1.6T"
    assert ok("GCV4 12 To 20T", vehicle_class="gcv", gvw_t=15, age=1)
    assert ok("GCV4 2.5 T and Above", vehicle_class="gcv", gvw_t=2.5, age=1)
    assert ok("GCV4 upto 2.5T upto 0-2 years", vehicle_class="gcv", gvw_t=2.5, age=2)
    assert ok("GCV4 3.5 To 7.5T-Petrol/CNG", vehicle_class="gcv", gvw_t=5, fuel="cng")
    assert not ok("GCV4 3.5 To 7.5T-Others", vehicle_class="gcv", gvw_t=5, fuel="cng")


def test_three_wheelers_and_ev() -> None:
    assert ok("GCV3", vehicle_class="gcv_3w")
    assert ok("PCV3W diesel Greater than 5 years", vehicle_class="pcv_3w", fuel="diesel", age=6)
    assert ok("PCV3W non-diesel Age 3-5", vehicle_class="pcv_3w", fuel="cng", age=4)
    assert not ok("PCV3W non-diesel Age 3-5", vehicle_class="pcv_3w", fuel="diesel", age=4)
    assert ok("PCV3W non-diesel 3+1 seater", vehicle_class="pcv_3w", fuel="petrol", seating_capacity=4)
    assert ok("E-Rickshaw Age 2+", vehicle_class="pcv_3w", fuel="electric", age=3)
    assert ok("E-Loaders", vehicle_class="gcv_3w", fuel="electric")
    assert ok(
        "PCV3W non-diesel (Kolkata RTOs)", vehicle_class="pcv_3w", fuel="cng", rto_location="KOLKATA (WB01)"
    )
    assert not ok(
        "PCV3W non-diesel (Excluding Kolkata RTOs)",
        vehicle_class="pcv_3w",
        fuel="cng",
        rto_location="KOLKATA (WB01)",
    )


def test_misc_tractor_jcb() -> None:
    assert ok("Tractor 6+ years", vehicle_class="tractor", age=7)
    assert ok("Tractor 0 to 5 years", vehicle_class="tractor", age=0)
    assert ok("Tractor >10 years", vehicle_class="tractor", age=11)
    assert ok("Misc D Age 0-5", vehicle_class="misc_d", age=2)
    assert ok("JCB age 1+", vehicle_class="misc_d", body_type="JCB 3DX", age=2)
    assert ok(
        "Backhoe loader, Forklift, Excavator, and loader age 0",
        vehicle_class="misc_d",
        body_type="FORKLIFT",
        age=0,
    )
    assert ok("PCV4 wheeler greater than 9 seater ", vehicle_class="pcv_taxi", seating_capacity=12)


@pytest.mark.parametrize(
    ("label", "base"),
    [
        ("GCV4 upto 2.5T (Low CD2 RTOs @ 10% CD2)", {"vehicle_class": "gcv", "gvw_t": 2.0}),
        ("GCV4 upto 2.5T (Declined RTOs)", {"vehicle_class": "gcv", "gvw_t": 2.0}),
        ("Misc D (only for selctive body types)", {"vehicle_class": "misc_d"}),
        ("Tractor 0 year - High HP", {"vehicle_class": "tractor", "age": 0}),
    ],
)
def test_undefined_part_is_reported_and_the_base_still_parsed(label: str, base: dict) -> None:  # type: ignore[type-arg]
    seg = parse_cv_segment(label)
    assert isinstance(seg, CvSegment) and seg.undefined and not seg.catch_all
    assert all(d in base and dim_matches(w, base[d]) for d, w in seg.dims), seg.dims


@pytest.mark.parametrize("label", ["GCV4 excl above", "All other segments of PCV, MiscD, Tractor"])
def test_catch_all_rows(label: str) -> None:
    seg = parse_cv_segment(label)
    assert isinstance(seg, CvSegment) and seg.catch_all and seg.undefined


def test_unknown_label_is_reported() -> None:
    assert isinstance(parse_cv_segment("Hovercraft deluxe"), str)
