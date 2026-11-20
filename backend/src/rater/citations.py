"""Citation formats (spec Design > Result JSON). Sheet names and files are kept byte-for-byte.

- policy:   `<file> · page N`
- XLSX:     `<file> · '<sheet>'!<range>`
- PDF grid: `<file> · page N · table '<name>' · row '<label>'`

Grid `file` values are paths relative to `insurance-rater-agent-challenge/`.
"""

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class PolicyCite:
    file: str
    page: int

    def render(self) -> str:
        return f"{self.file} · page {self.page}"

    def to_dict(self) -> dict[str, Any]:
        return {"type": "policy", **asdict(self)}


@dataclass(frozen=True)
class XlsxCite:
    file: str
    sheet: str
    range: str

    def render(self) -> str:
        return f"{self.file} · '{self.sheet}'!{self.range}"

    def to_dict(self) -> dict[str, Any]:
        return {"type": "xlsx", **asdict(self)}


@dataclass(frozen=True)
class PdfGridCite:
    file: str
    page: int
    table: str
    row: str

    def render(self) -> str:
        return f"{self.file} · page {self.page} · table '{self.table}' · row '{self.row}'"

    def to_dict(self) -> dict[str, Any]:
        return {"type": "pdf_grid", **asdict(self)}


GridCite = XlsxCite | PdfGridCite
