import re

from rater.bundle import BUNDLE_ROOT
from rater.grids.pdfgrid import pdf_lines

HDFC = next((BUNDLE_ROOT / "raters/hdfc-ergo").rglob("*.pdf"))
PCT = re.compile(r"^\d+(\.\d+)?%$")


def test_pdf_table_rows_have_labels() -> None:
    lines = pdf_lines(HDFC)
    assert {ln.page for ln in lines} == {1, 2}
    rate_rows = [ln for ln in lines if len(ln.words) == 7 and all(PCT.match(w.text) for w in ln.words[1:])]
    # Each rate row starts with its slab label, then six percentages ordered left to right.
    assert rate_rows, "no rate rows found"
    for ln in rate_rows:
        assert not PCT.match(ln.words[0].text)
        xs = [w.x0 for w in ln.words]
        assert xs == sorted(xs)


def test_lines_are_top_to_bottom_per_page() -> None:
    lines = pdf_lines(HDFC)
    for page in (1, 2):
        ys = [ln.y for ln in lines if ln.page == page]
        assert ys == sorted(ys)
