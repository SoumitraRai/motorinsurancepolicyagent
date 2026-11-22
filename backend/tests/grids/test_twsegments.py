from rater.grids.model import NotIn, dim_matches
from rater.grids.twsegments import parse_tw_segment


def matches(label: str, siblings: list[str] | None = None, **facts) -> bool:  # type: ignore[no-untyped-def]
    """True if any alternative the label expands to matches the facts."""
    for alt in parse_tw_segment(label, siblings or [label]):
        if all(d in facts and dim_matches(w, facts[d]) for d, w in alt):
            return True
    return False


def test_scooter_motorcycle_and_ev() -> None:
    assert matches("SCOOTER", tw_type="scooter")
    assert not matches("SCOOTER", tw_type="motorcycle")
    assert matches("MC", tw_type="motorcycle")
    assert matches("SCOOTER/MC", tw_type="motorcycle") and matches("SCOOTER/MC", tw_type="scooter")
    assert matches("SC/EV", tw_type="scooter", fuel="petrol") and matches(
        "SC/EV", tw_type="motorcycle", fuel="electric"
    )
    assert matches("SC_EV", tw_type="scooter", fuel="electric")
    assert matches("SC", tw_type="scooter")


def test_cc_bands_for_motorcycles() -> None:
    assert matches("MC <=155", tw_type="motorcycle", cc=150) and not matches(
        "MC <=155", tw_type="motorcycle", cc=160
    )
    assert matches("MC >155", tw_type="motorcycle", cc=160)
    assert matches("MC>350", tw_type="motorcycle", cc=500) and not matches(
        "MC>350", tw_type="motorcycle", cc=350
    )
    assert matches("MC_180-350_Others", ["MC_180-350_Others"], tw_type="motorcycle", cc=200, make="BAJAJ")
    assert not matches("MC_180-350_Others", tw_type="motorcycle", cc=150, make="BAJAJ")
    assert matches("< =350", tw_type="motorcycle", cc=350) and matches("> 350", tw_type="motorcycle", cc=351)


def test_make_groups_and_others_relative_to_siblings() -> None:
    sib = ["MC <= 180 Others", "MC <= 180 Hero/Honda"]
    assert matches("MC <= 180 Hero/Honda", sib, tw_type="motorcycle", cc=125, make="HERO MOTOCORP")
    assert matches("MC <= 180 Hero/Honda", sib, tw_type="motorcycle", cc=125, make="HONDA")
    assert not matches("MC <= 180 Others", sib, tw_type="motorcycle", cc=125, make="HONDA")
    assert matches("MC <= 180 Others", sib, tw_type="motorcycle", cc=125, make="BAJAJ")
    assert matches("MC_180-350_RE", tw_type="motorcycle", cc=350, make="ROYAL ENFIELD")
    assert not matches("MC_180-350_Other than RE", tw_type="motorcycle", cc=350, make="ROYAL ENFIELD")
    assert matches("MC_180-350_Other than RE", tw_type="motorcycle", cc=300, make="KTM")
    assert matches(
        "MC_180-350_HONDA/JAWA/Avenger", tw_type="motorcycle", cc=220, make="BAJAJ", model="AVENGER 220"
    )
    assert matches("MC_180-350_HONDA/JAWA/Avenger", tw_type="motorcycle", cc=300, make="JAWA", model="42")


def test_ev_power_bands() -> None:
    assert matches("< 3 KW", fuel="electric", power_kw=2.5) and not matches(
        "< 3 KW", fuel="electric", power_kw=3
    )
    assert matches("3-7 KW", fuel="electric", power_kw=5)
    assert matches(">7 KW", fuel="electric", power_kw=8) and matches("> 3 KW", fuel="electric", power_kw=4)
    assert not matches("3-7 KW", fuel="petrol", power_kw=5)


def test_all_matches_anything() -> None:
    assert parse_tw_segment("All", ["All"]) == [()]


def test_unknown_label_raises() -> None:
    import pytest

    with pytest.raises(ValueError):
        parse_tw_segment("Quadricycle deluxe", ["Quadricycle deluxe"])


def test_others_uses_notin() -> None:
    alts = parse_tw_segment("MC <= 180 Others", ["MC <= 180 Others", "MC <= 180 Hero/Honda"])
    makes = [w for alt in alts for d, w in alt if d == "make"]
    assert makes and isinstance(makes[0], NotIn) and {"HERO MOTOCORP", "HONDA"} <= set(makes[0].values)


def test_bare_ev() -> None:
    assert matches("EV", fuel="electric") and not matches("EV", fuel="petrol")
