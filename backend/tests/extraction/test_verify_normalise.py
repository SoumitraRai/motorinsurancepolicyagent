from rater.extraction.normalise import RawField, normalise
from rater.extraction.ocr import PageEvidence
from rater.extraction.verify import verify_quote


def page(text_layer: str = "", rapid: str = "", tess: str = "", n: int = 1) -> PageEvidence:
    return PageEvidence(page=n, text_layer=text_layer, by_engine={"rapidocr": rapid, "tesseract": tess})


def test_verify_both_one_none() -> None:
    p = page(rapid="CubicCapacityWatts1493", tess="Cubic Capacity Watts 1493 Seats 7")
    assert verify_quote("Cubic Capacity Watts 1493", p) == "verified_both"
    assert verify_quote("Seats 7", page(rapid="nothing", tess="Seats 7")) == "verified_one"
    assert verify_quote("Seats 9", p) == "unverified"
    assert verify_quote("cubic  CAPACITY watts 1493", p) == "verified_both"  # case and spacing ignored


def test_text_layer_wins() -> None:
    assert verify_quote("Fuel Type Petrol", page(text_layer="Fuel Type   Petrol")) == "text_layer"


def raw(value: str | None, quote: str | None = None, pg: int | None = 1) -> RawField:
    return RawField(value=value, page=pg, quote=quote if quote is not None else value)


def run(**fields: RawField):  # type: ignore[no-untyped-def]
    pages = [
        page(
            rapid=" ".join(f.quote or "" for f in fields.values()),
            tess=" ".join(f.quote or "" for f in fields.values()),
        )
    ]
    return normalise(fields, pages, "upload.pdf")


def test_placeholder_date_unknown() -> None:
    f = run(manufactureYear=raw("0001-01-01", "Year of Mfg. 0001-01-01"))
    assert f.manufacture_year.value is None and "placeholder" in (f.manufacture_year.note or "")


def test_rto_normalised() -> None:
    f = run(registrationNumber=raw("ZZ-07-CD-1234", "Registration No ZZ-07-CD-1234"))
    assert f.rto.value == "ZZ07"
    g = run(rto=raw("ab 3", "RTO Code AB 3"))
    assert g.rto.value == "AB03"


def test_percent_beside_rupee_not_rate() -> None:
    f = run(odPremium=raw("(%) 2433", "Own Damage Premium(a) (%) 2433"), ncb=raw("(%) 2433", "(%) 2433"))
    assert f.od_premium.value == 2433.0
    assert f.ncb.value is None  # a "%" next to a rupee amount is never a rate or a percentage


def test_money_and_dates() -> None:
    f = run(netPremium=raw("8,535.00"), policyStartDate=raw("29 Mar, 2026"), issueDate=raw("24-Mar-2026"))
    assert f.net_premium.value == 8535.0
    assert f.policy_start_date.value == "2026-03-29" and f.issue_date.value == "2026-03-24"
    assert run(policyStartDate=raw("29/03/2026")).policy_start_date.value == "2026-03-29"


def test_watermark_ignored_for_policy_type() -> None:
    title = raw("Private Car Package Policy", "Private Car Package Policy Schedule")
    assert run(policyType=title).policy_type.value == "comprehensive"
    satp = raw("Liability Only Policy", "Digit Private Car Liability Only Policy")
    assert run(policyType=satp).policy_type.value == "satp"
    # A "liability only" title that comes with an OD premium contradicts itself (SR9): not guessed.
    clash = run(policyType=satp, odPremium=raw("5,064.16", "Basic OD 5,064.16"))
    assert clash.policy_type.value is None and "contradict" in (clash.policy_type.note or "")


def test_two_ncb_figures_applied_one_wins() -> None:
    f = run(ncb=raw("35", "Less: No Claim Bonus (35%)"), previousNcb=raw("25", "NCB 25%"))
    assert f.ncb.value == 35.0 and f.previous_ncb.value == 25.0
    assert run(ncb=raw("135", "NCB 135%")).ncb.value is None  # not a valid NCB


def test_business_type_derived() -> None:
    same = run(insurer=raw("Acme General Insurance"), previousInsurer=raw("ACME GENERAL INSURANCE CO"))
    assert same.business_type.value == "renewal" and same.business_type.verification == "derived"
    other = run(insurer=raw("Acme General Insurance"), previousInsurer=raw("Zenith Insurance"))
    assert other.business_type.value == "rollover"
    new = run(businessType=raw("New Business"))
    assert new.business_type.value == "new"
    assert run(insurer=raw("Acme General Insurance")).business_type.value is None


def test_vehicle_class_fuel_make_cc() -> None:
    f = run(
        vehicleClass=raw("Private Car"),
        fuel=raw("Bi-Fuel (Petrol + CNG)"),
        make=raw("Maruti Suzuki"),
        cc=raw("1,197 CC"),
    )
    assert (f.vehicle_class.value, f.fuel.value, f.make.value, f.cc.value) == (
        "private_car",
        "cng",
        "MARUTI",
        1197,
    )
    assert run(vehicleClass=raw("Two Wheeler")).vehicle_class.value == "two_wheeler"
    assert run(fuel=raw("Battery Electric")).fuel.value == "electric"


def test_add_ons_and_cpa() -> None:
    f = run(addOns=raw("Zero Depreciation, Engine Protect"), cpaCover=raw("Yes"))
    assert f.add_ons.value == ["Zero Depreciation", "Engine Protect"] and f.cpa_cover.value == "yes"
    assert run(addOns=raw("None")).add_ons.value == []


def test_page_citation_and_verification_recorded() -> None:
    f = run(cc=raw("1197", "Cubic Capacity 1197", pg=1))
    assert f.cc.policy_citation == "upload.pdf · page 1" and f.cc.verification == "verified_both"
    unseen = normalise({"cc": raw("1197", "Cubic Capacity 1197")}, [page(rapid="x", tess="y")], "upload.pdf")
    assert unseen.cc.verification == "unverified" and unseen.cc.confidence == "low"
