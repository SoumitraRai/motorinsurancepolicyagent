from rater.citations import PdfGridCite, PolicyCite, XlsxCite

GODIGIT = "raters/godigit/march-2026/Large Insurance Brokers Mar'26 - Shared.xlsx"


def test_policy_cite_render() -> None:
    assert PolicyCite("upload.pdf", 3).render() == "upload.pdf · page 3"


def test_render_preserves_sheet_spaces() -> None:
    assert XlsxCite(GODIGIT, "4W  RTO", "B9:F9").render() == f"{GODIGIT} · '4W  RTO'!B9:F9"
    assert XlsxCite(GODIGIT, "School & Staff Bus ", "C5").render() == f"{GODIGIT} · 'School & Staff Bus '!C5"


def test_pdf_grid_cite_render() -> None:
    c = PdfGridCite("raters/hdfc-ergo/feb-2025/grid.pdf", 1, "Zone 2", ">10-50k")
    assert c.render() == "raters/hdfc-ergo/feb-2025/grid.pdf · page 1 · table 'Zone 2' · row '>10-50k'"


def test_structured_form_keeps_exact_values() -> None:
    assert XlsxCite(GODIGIT, "4W  RTO", "B9").to_dict() == {
        "type": "xlsx",
        "file": GODIGIT,
        "sheet": "4W  RTO",
        "range": "B9",
    }
    assert PdfGridCite("g.pdf", 2, "Zone 1", "<10k").to_dict() == {
        "type": "pdf_grid",
        "file": "g.pdf",
        "page": 2,
        "table": "Zone 1",
        "row": "<10k",
    }
    assert PolicyCite("p.pdf", 1).to_dict() == {"type": "policy", "file": "p.pdf", "page": 1}
