import shutil
from pathlib import Path

import pytest

from rater.bundle import BUNDLE_ROOT, BundleIntegrityError
from rater.grids.registry import ALIASES, load_all
from rater.resolve.select import canonical_insurer


def test_load_all_verifies_and_loads_every_wave1_grid() -> None:
    gs = load_all(BUNDLE_ROOT)
    ids = {g.id for g in gs.grids}
    assert {
        "hdfc-ergo/pvt-car",
        "godigit/4W SATP",
        "godigit/4W New Business 1+3",
        "reliance/pvt-car",
        "tata-aig/Pvtcar",
    } <= ids
    two_wheelers = {
        "godigit/TW 1+1",
        "godigit/TW SATP",
        "godigit/TW 1+5",
        "godigit/2W Grid 5+5",
        "godigit/TW SAOD",
        "reliance/tw-scooter",
        "tata-aig/TW",
    }
    assert two_wheelers <= ids
    assert set(gs.aliases) == {g.insurer for g in gs.grids}


def test_tampered_bundle_refuses_to_load(tmp_path: Path) -> None:
    root = tmp_path / "bundle"
    shutil.copytree(BUNDLE_ROOT, root)
    (root / "challenge.md").write_text("tampered")
    with pytest.raises(BundleIntegrityError):
        load_all(root)


@pytest.mark.parametrize(
    ("text", "insurer"),
    [
        ("Go Digit General Insurance Ltd.", "Go Digit"),
        ("DIGIT GENERAL INSURANCE", "Go Digit"),
        ("Reliance General Insurance Company Limited", "Reliance"),
        ("IndusInd General Insurance", "Reliance"),
        ("HDFC ERGO General Insurance Company Limited", "HDFC ERGO"),
        ("TATA AIG GENERAL INSURANCE CO.LTD.", "Tata AIG"),
        ("Bajaj Allianz General Insurance", None),
    ],
)
def test_insurer_aliases(text: str, insurer: str | None) -> None:
    from rater.grids.model import GridSet

    assert canonical_insurer(text, GridSet(grids=(), aliases=ALIASES)) == insurer
