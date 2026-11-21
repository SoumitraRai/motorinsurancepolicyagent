"""Re-open a cited source and confirm it holds the value a rule claims (AC2, AC21).

XLSX: the cited cell (first cell of a range) must hold `raw` as a stored value.
PDF grid: within the cited table on the cited page, the line for the cited row must contain `raw`.
"""

from functools import lru_cache
from pathlib import Path
from typing import Any

from rater.citations import PdfGridCite, XlsxCite
from rater.grids.pdfgrid import Line, pdf_lines
from rater.grids.xlsx import Workbook


@lru_cache(maxsize=8)
def _workbook(path: Path) -> Workbook:
    return Workbook(path)


@lru_cache(maxsize=8)
def _lines(path: Path) -> tuple[Line, ...]:
    return tuple(pdf_lines(path))


def _same(a: Any, b: Any) -> bool:
    if a is None or b is None:
        return a is b
    try:
        return float(a) == float(b)
    except (TypeError, ValueError):
        return " ".join(str(a).split()) == " ".join(str(b).split())


def _table_lines(lines: tuple[Line, ...], page: int, table: str) -> list[Line]:
    """Lines after the table's title line on `page`, up to the next line that starts another `Zone` table."""
    title = table.split(" / ")[0].strip()
    on_page = [ln for ln in lines if ln.page == page]
    for i, ln in enumerate(on_page):
        if ln.text.strip() == title:
            out = []
            for nxt in on_page[i + 1 :]:
                if nxt.text.strip().startswith(title.split()[0]) and nxt.text.strip() != title:
                    break
                out.append(nxt)
            return out
    return on_page  # tables without a title line (e.g. the state table) span the page


def check(root: Path, cite: XlsxCite | PdfGridCite, raw: Any) -> bool:
    if isinstance(cite, XlsxCite):
        coord = cite.range.split(":")[0]
        return _same(_workbook(root / cite.file).sheet(cite.sheet).value(coord), raw)
    lines = _table_lines(_lines(root / cite.file), cite.page, cite.table)
    for ln in lines:
        is_row = bool(ln.words) and (ln.words[0].text == cite.row or cite.row in ln.text)
        if is_row and (any(_same(w.text, raw) for w in ln.words) or str(raw) in ln.text):
            return True
    return False
