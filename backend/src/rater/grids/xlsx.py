"""Read XLSX grids by stored (cached) values only (intent B1, spec SR12).

Formulas are read only to recognise cells that are not data: a formula whose result was never stored
(`MISSING`), aggregate rows (`SUBTOTAL`/`SUM`), and error values such as `#REF!`.
"""

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import openpyxl


class _Missing:
    def __repr__(self) -> str:
        return "MISSING"


MISSING: Any = _Missing()
_AGGREGATES = ("=SUBTOTAL(", "=SUM(", "=AVERAGE(", "=COUNT(")


class Sheet:
    def __init__(self, values: Any, formulas: Any) -> None:
        self.name: str = values.title
        self._v = values
        self._f = formulas

    def formula(self, coord: str) -> str | None:
        f = self._f[coord].value
        return f if isinstance(f, str) and f.startswith("=") else None

    def value(self, coord: str) -> Any:
        v = self._v[coord].value
        if v is None and self.formula(coord) is not None:
            return MISSING
        return v

    def is_error(self, coord: str) -> bool:
        v = self._v[coord].value
        return isinstance(v, str) and v.startswith("#") and v.endswith(("!", "?", "/0!", "A")) and v.isupper()

    def is_aggregate(self, coord: str) -> bool:
        f = self.formula(coord)
        return f is not None and f.upper().startswith(_AGGREGATES)

    def cells(self) -> Iterator[tuple[str, Any]]:
        """Non-empty cells in row order, as (coordinate, value); formula-without-cache cells yield MISSING."""
        for row in self._f.iter_rows():
            for cell in row:
                value = self.value(cell.coordinate)
                if value is not None:
                    yield cell.coordinate, value

    @property
    def max_row(self) -> int:
        return int(self._v.max_row)

    @property
    def max_column(self) -> int:
        return int(self._v.max_column)


class Workbook:
    """Both views of one workbook. Callers should drop it once rules are built (memory, plan T10)."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._values = openpyxl.load_workbook(path, data_only=True)
        self._formulas = openpyxl.load_workbook(path, data_only=False)

    @property
    def sheet_names(self) -> list[str]:
        return list(self._values.sheetnames)

    def sheet(self, name: str) -> Sheet:
        return Sheet(self._values[name], self._formulas[name])

    def close(self) -> None:
        self._values.close()
        self._formulas.close()
