"""Dimension values from facts, and mapping into grid vocabulary (spec SR16).

Mapping uses only the grid's own tables; a printed location never overrides the grid's mapping.
"""

from datetime import date
from typing import Any

from rater.facts import Facts
from rater.grids.model import Grid
from rater.resolve.common import Refusal, Step

# dimension -> facts it is computed from
SOURCES: dict[str, tuple[str, ...]] = {
    "age": ("manufacture_year", "policy_start_date"),
    "ncb_flag": ("ncb",),
}


def _year(value: Any) -> int | None:
    if isinstance(value, date):
        return value.year
    if isinstance(value, str) and len(value) >= 4 and value[:4].isdigit():
        return int(value[:4])
    if isinstance(value, int):
        return value
    return None


def dim_value(name: str, facts: Facts, grid: Grid, mapped: dict[str, str]) -> tuple[Any, tuple[str, ...]]:
    """The value of a rule dimension for this policy, and the facts it came from. None when unknown."""
    if name in mapped:
        return mapped[name], ()
    if name == "age":
        made, start = _year(facts.value("manufacture_year")), _year(facts.value("policy_start_date"))
        return (start - made if made is not None and start is not None else None), SOURCES["age"]
    if name == "ncb_flag":
        if grid.new_business_counts_as_ncb and facts.value("business_type") == "new":
            return "ncb", ("business_type",)
        ncb = facts.value("ncb")
        return (None if ncb is None else ("ncb" if float(ncb) > 0 else "no_ncb")), SOURCES["ncb_flag"]
    value = facts.get(name).value if name in type(facts).model_fields else None
    return value, (name,)


def apply_mappings(facts: Facts, grid: Grid) -> tuple[dict[str, str], list[Step], set[str]] | Refusal:
    mapped: dict[str, str] = {}
    steps: list[Step] = []
    used: set[str] = set()
    for table in grid.mappings:
        source, srcs = dim_value(table.source, facts, grid, mapped)
        if source is None:
            return Refusal(
                "ambiguous",
                f"{table.name}: the policy's {table.source} could not be read.",
                missing=srcs or (table.source,),
            )
        rows = table.lookup(str(source))
        values = sorted({r.value for r in rows})
        if not rows:
            return Refusal(
                "unsupported", f"{table.name}: '{source}' is not listed in the grid's mapping table."
            )
        if len(values) > 1:
            return Refusal(
                "ambiguous",
                f"{table.name}: '{source}' maps to more than one value ({', '.join(values)}).",
                cites=tuple(r.cite for r in rows),
            )
        mapped[table.target] = values[0]
        used.update(srcs)
        steps.append(
            Step(
                "map",
                f"{table.name}: {source} maps to {values[0]}.",
                facts=srcs,
                cites=tuple(r.cite for r in rows),
            )
        )
    return mapped, steps, used
