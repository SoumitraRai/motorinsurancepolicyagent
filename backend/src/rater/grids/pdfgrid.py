"""Read a PDF grid's text layer as positioned lines (spec SR13). Adapters build tables from these."""

from dataclasses import dataclass
from pathlib import Path

import pdfplumber


@dataclass(frozen=True)
class Word:
    text: str
    x0: float
    x1: float


@dataclass(frozen=True)
class Line:
    page: int
    y: float
    words: tuple[Word, ...]

    @property
    def text(self) -> str:
        return " ".join(w.text for w in self.words)


def pdf_lines(path: Path, y_tolerance: float = 3.0) -> list[Line]:
    """Words grouped into lines (same baseline within `y_tolerance`), top to bottom, left to right."""
    lines: list[Line] = []
    with pdfplumber.open(path) as pdf:
        for page_no, page in enumerate(pdf.pages, start=1):
            words = sorted(page.extract_words(), key=lambda w: (w["top"], w["x0"]))
            groups: list[list[dict]] = []  # type: ignore[type-arg]
            for w in words:
                if groups and abs(groups[-1][0]["top"] - w["top"]) <= y_tolerance:
                    groups[-1].append(w)
                else:
                    groups.append([w])
            for g in groups:
                g.sort(key=lambda w: w["x0"])
                lines.append(
                    Line(
                        page=page_no,
                        y=round(float(g[0]["top"]), 1),
                        words=tuple(Word(w["text"], float(w["x0"]), float(w["x1"])) for w in g),
                    )
                )
    return lines
