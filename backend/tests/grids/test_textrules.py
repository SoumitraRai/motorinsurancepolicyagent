import pytest

from rater.grids.textrules import classify

# Real T&C and note lines from the supplied grids, with the kind each must classify as.
# The expected value is a classification, never a rate (NN5).
CASES = [
    # Reliance `PRIVATE CAR COMP, SAOD & STP` column H
    ("payout will made on OD Premium", "private_car", "basis", None),
    (
        "Payout for < 1000 CC, PO will be 5% lesser than the above Grid",
        "private_car",
        "policy_condition",
        ("reduce", 5.0),
    ),
    (
        "Standlone ZD policies 2.5%will be redused from the above Grid",
        "private_car",
        "policy_condition",
        ("reduce", 2.5),
    ),
    ("EW of Pvivate car will be Flat 20% Payout", "private_car", "out_of_scope", None),
    (
        "Addon Bundle (Tyre / RTI) if Sourced, 2.5% Additional Payout Shall be offered",
        "private_car",
        "policy_condition",
        ("add", 2.5),
    ),
    # Go Digit `4W SATP` column F
    ("Few RTOs for 1000-1500CC segment are declined", "private_car", "undefined_decline", None),
    ("Few RTOs for all age are declined", "private_car", "undefined_decline", None),
    ("1000-1500CC and <10 age is declined", "private_car", "policy_condition", ("decline", None)),
    ("More than 1500CC and 10+age is declined", "private_car", "policy_condition", ("decline", None)),
    # Go Digit CV notes (broker volume)
    (
        "Additional 2.5% CD2 can be offered to partners with volume of 10 Lac monthly.",
        "gcv",
        "broker_side",
        None,
    ),
    ("Additional 1% CD2 for partner doing more than 10 lakhs monthly business.", "gcv", "broker_side", None),
    (
        "Additional 4% CD2 will be released for IMDs who achieve a monthly volume of 2.5 lakhs",
        "gcv",
        "broker_side",
        None,
    ),
    # Reliance T&C sheet
    ("2.5% of Motor or 10.0k of synergy business", "private_car", "broker_side", None),
    ("Guideline of M&HCV(>= 12T) PAN india:-", "private_car", "out_of_scope", None),
    # HDFC ERGO footnotes
    (
        "Slab will be calculated basis comprehensive + SAOD GWP on PVT CAR "
        "(SATP premium is excluded for slab achievement)",
        "private_car",
        "slab_basis",
        None,
    ),
    ("*Non Petrol includes Diesel, CNG, LPG", "private_car", "definition", None),
    ("#New Business will be considered as NCB", "private_car", "definition", None),
    ("# EV and Hybrid is to be considered in Petrol Grid", "private_car", "definition", None),
    # Tata AIG `General Guidelines`
    (
        "Payout % for Pvt Car- SATP on Net Premium; Package and SAOD on OD premium",
        "private_car",
        "basis",
        None,
    ),
    (
        "Only Base Commission Needs to be updated in the Following sheet, "
        "Additionally we have created GWP based Rule Incremental COA",
        "private_car",
        "broker_side",
        None,
    ),
]


@pytest.mark.parametrize(("text", "product", "kind", "effect"), CASES)
def test_classify_examples(
    text: str, product: str, kind: str, effect: tuple[str, float | None] | None
) -> None:
    got = classify(text, product)
    assert got.kind == kind, text
    if effect is not None:
        assert (got.effect, got.percent) == effect


def test_unknown_line_is_unclassified() -> None:
    assert (
        classify("Kindly coordinate with the regional office for approvals", "private_car").kind
        == "unclassified"
    )
