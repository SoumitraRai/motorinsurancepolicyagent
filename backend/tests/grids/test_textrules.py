import pytest

from rater.grids.textrules import classify

# Real T&C and note lines from the supplied grids, with the kind each must classify as.
# The expected value is a classification, never a rate (NN5).
CASES = [
    # Reliance `PRIVATE CAR COMP, SAOD & STP` column H
    ("payout will made on OD Premium", "private_car", "basis", None),
    # Tata AIG `CV`!A2
    ("All % on Net Premium", "gcv", "basis", None),
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


def test_post_issue_recoveries() -> None:
    for line in (
        "4. NCB if found to be falsified, 2.5% PO shall be recovered.",
        "2. For any discrepancy in risk attributes viz; RTO code ... full commision shall be recoverable.",
    ):
        assert classify(line, "private_car").kind == "post_issue"
    cpa = classify(
        "3.CPA is mandatoryfor all policies,Else 1% PO shall be deducted from the overall PO.", "private_car"
    )
    assert (cpa.kind, cpa.effect, cpa.percent) == ("policy_condition", "reduce", 1.0)


TATA_GUIDELINES = [
    ("Standard Grid to be inputted centally", "process"),
    ("Payout % for CV on Net Premium", "out_of_scope"),
    ("Payout% for TW to be applied on New  (1+5 premium) + Old(1+1 premium)", "out_of_scope"),
    ("LTTP not be considered for premium slab as well as payout %", "basis"),
    (
        "RTO Cluster identification- for all policies_RTO mapped on policy; for Brand New- If RTO is not "
        "available; producer tagged to branch and RTO of that branch to be used",
        "definition",
    ),
    ("Sequence for calculation", "process"),
    ("a. Policy specific", "process"),
    ("e. Standard Grid", "process"),
    ("Producers not on covered in pt 6 a/b/c shall by default fall under standard grid", "process"),
    (
        "Cancellation/Endorsement: For the purpose of Business Slab calculation Net premium will be "
        "considered "
        "post effect to cancellation/endorsement premium",
        "process",
    ),
]


@pytest.mark.parametrize(("text", "kind"), TATA_GUIDELINES)
def test_tata_guideline_lines(text: str, kind: str) -> None:
    assert classify(text, "private_car").kind == kind


RELIANCE_TW = [
    ("Tw Scooter Fresh (1+5 & 5+5):  EV Makes - FLAT 25 % PO", "policy_condition", ("flat", 25.0)),
    ("Tw Scooter Fresh (1+5 & 5+5):  Yamaha & HMC- above grid (-)2.5%", "policy_condition", ("reduce", 2.5)),
    (
        "Tw Scooter Fresh (1+5 & 5+5): RTO regions: Kolhapur, Mysore, Mangolore, "
        "West Bengal (Excluding Kolkata) - "
        "PO Will Be FLAT 20%",
        "policy_condition",
        ("flat", 20.0),
    ),
    ("Grid Not applicable for Bike Comp (1+1 / 1+5 / 5+5) & STP", "definition", None),
    (
        "Payout Will be madeon 1/2 basis , 50%1st yearand 50% 2nd year(1st LT Posting) "
        "-applicable for Tw Fresh "
        "Business",
        "process",
        None,
    ),
    ("Tw- Scooter Contest ", "broker_side", None),
    ("Minimum GWP ( January ) in Lakhs", "broker_side", None),
]


@pytest.mark.parametrize(("text", "kind", "effect"), RELIANCE_TW)
def test_reliance_tw_lines(text: str, kind: str, effect: tuple[str, float] | None) -> None:
    got = classify(text, "two_wheeler")
    assert got.kind == kind, text
    if effect:
        assert (got.effect, got.percent) == effect
