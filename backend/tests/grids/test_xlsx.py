from rater.bundle import BUNDLE_ROOT
from rater.grids.xlsx import MISSING, Workbook

GODIGIT = BUNDLE_ROOT / "raters/godigit/march-2026/Large Insurance Brokers Mar'26 - Shared.xlsx"
TATA = BUNDLE_ROOT / "raters/tata-aig/march-2026/Tata AIG Standard Grid_Communication_Mar'26_F_v2_0212.xlsx"


def test_missing_cache_is_missing() -> None:
    sheet = Workbook(GODIGIT).sheet("School & Staff Bus ")
    missing = [coord for coord, value in sheet.cells() if value is MISSING]
    assert len(missing) == 7
    for coord in missing:
        assert sheet.formula(coord) is not None  # a formula whose result was never stored


def test_cached_values_not_formulas() -> None:
    sheet = Workbook(GODIGIT).sheet("4W SATP")
    coord = "A59"  # helper column `=B59&C59&D59`
    assert sheet.formula(coord) == "=B59&C59&D59"
    assert isinstance(sheet.value(coord), str) and not str(sheet.value(coord)).startswith("=")


def test_ref_and_subtotal_not_data() -> None:
    sheet = Workbook(TATA).sheet("Pvtcar")
    assert sheet.is_error("A3")  # '#REF!'
    assert sheet.is_aggregate("M567")  # =SUBTOTAL(9,M6:M565)
    assert not sheet.is_aggregate("M6")
    assert not sheet.is_error("M6")


def test_sheet_names_exact() -> None:
    names = Workbook(GODIGIT).sheet_names
    assert "4W  RTO" in names and "School & Staff Bus " in names
