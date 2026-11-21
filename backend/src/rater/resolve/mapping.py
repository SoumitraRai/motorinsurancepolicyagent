"""Dimension values from facts, and mapping into grid vocabulary (spec SR16).

Mapping uses only the grid's own tables; a printed location never overrides the grid's mapping.
"""

from datetime import date
from typing import Any

from rater.facts import Facts
from rater.grids import geo
from rater.grids.model import CitySplitTable, Grid, MappingRow, RtoRegionTable, norm_key
from rater.resolve.common import Refusal, Step
from rater.resolve.confidence import Cap

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
    if name == "has_add_ons":
        add_ons = facts.value("add_ons")
        return (None if add_ons is None else ("yes" if len(add_ons) > 0 else "no")), ("add_ons",)
    if name == "ncb_flag":
        if grid.new_business_counts_as_ncb and facts.value("business_type") == "new":
            return "ncb", ("business_type",)
        ncb = facts.value("ncb")
        return (None if ncb is None else ("ncb" if float(ncb) > 0 else "no_ncb")), SOURCES["ncb_flag"]
    value = facts.get(name).value if name in type(facts).model_fields else None
    return value, (name,)


def _city_split(
    table: CitySplitTable, facts: Facts
) -> tuple[list[MappingRow], tuple[str, ...], str] | Refusal:
    rto = facts.value("rto")
    if rto is None:
        return Refusal("ambiguous", f"{table.name}: the policy's RTO could not be read.", missing=("rto",))
    state = geo.state_of(str(rto))
    if state is None:
        return Refusal(
            "unsupported", f"{table.name}: '{rto}' does not start with an Indian state code ({geo.SOURCE})."
        )
    key = norm_key(state)
    whole = [r for r in table.rows if "|" not in r.key and norm_key(r.key) == key]
    if whole:
        return whole, ("rto",), state
    prefix = state + "|"
    split = [r for r in table.rows if r.key.upper().startswith(prefix)]
    if not split:
        return Refusal("unsupported", f"{table.name}: {state} (from {rto}) is not listed in the grid.")
    location = facts.value("rto_location")
    if location is None:
        return Refusal(
            "ambiguous",
            f"{table.name}: {state} is split by city in the grid, and the policy's RTO "
            "location could not be read.",
            cites=tuple(r.cite for r in split),
            missing=("rto_location",),
        )
    loc = norm_key(location)
    cities = [r for r in split if not r.key.endswith("|*") and norm_key(r.key.split("|", 1)[1]) in loc]
    if not cities:
        cities = [r for r in split if r.key.endswith("|*")]
    if not cities:
        return Refusal(
            "unsupported",
            f"{table.name}: '{location}' ({state}) matches no city row in the grid.",
            cites=tuple(r.cite for r in split),
        )
    return cities, ("rto", "rto_location"), f"{state} / {location}"


def _rto_region(
    table: RtoRegionTable, facts: Facts
) -> tuple[list[MappingRow], tuple[str, ...], str] | Refusal:
    rto = facts.value("rto")
    if rto is None:
        return Refusal("ambiguous", f"{table.name}: the policy's RTO could not be read.", missing=("rto",))
    key = norm_key(str(rto))
    rows = [r for r in table.by_code if norm_key(r.key) == key]
    if rows:
        return rows, ("rto",), str(rto)
    state = geo.state_of(str(rto))
    if state is None:
        return Refusal(
            "unsupported",
            f"{table.name}: '{rto}' is not in the grid's RTO list and does not start "
            f"with an Indian state code ({geo.SOURCE}).",
        )
    rows = [r for r in table.by_state if norm_key(r.key) == norm_key(state)]
    if not rows:
        return Refusal(
            "unsupported",
            f"{table.name}: '{rto}' is not in the grid's RTO list, and no grid row covers {state}.",
        )
    return rows, ("rto",), f"{rto} ({state})"


def apply_mappings(
    facts: Facts, grid: Grid
) -> tuple[dict[str, str], list[Step], set[str], list[Cap]] | Refusal:
    mapped: dict[str, str] = {}
    steps: list[Step] = []
    used: set[str] = set()
    caps: list[Cap] = []
    for table in grid.mappings:
        if isinstance(table, RtoRegionTable):
            got_r = _rto_region(table, facts)
            if isinstance(got_r, Refusal):
                return got_r
            rows, srcs, shown = got_r
            source: Any = shown
        elif isinstance(table, CitySplitTable):
            got = _city_split(table, facts)
            if isinstance(got, Refusal):
                return got
            rows, srcs, shown = got
            source = shown
        else:
            source, srcs = dim_value(table.source, facts, grid, mapped)
            if source is None:
                if table.if_missing == "unsupported":
                    return Refusal("unsupported", f"{table.name}: {table.missing_reason}")
                return Refusal(
                    "ambiguous",
                    f"{table.name}: the policy's {table.source} could not be read.",
                    missing=srcs or (table.source,),
                )
            rows = table.lookup(str(source))
            if not rows:
                return Refusal(
                    "unsupported", f"{table.name}: '{source}' is not listed in the grid's mapping table."
                )
        values = sorted({r.value for r in rows})
        if len(values) > 1:
            return Refusal(
                "ambiguous",
                f"{table.name}: '{source}' maps to more than one value ({', '.join(values)}).",
                cites=tuple(r.cite for r in rows),
            )
        mapped[table.target] = values[0]
        used.update(srcs)
        notes = sorted({r.note for r in rows if r.note})
        caps.extend(r.cap for r in rows if r.cap is not None)
        steps.append(
            Step(
                "map",
                f"{table.name}: {source} maps to {values[0]}"
                + (f" ({'; '.join(notes)})" if notes else "")
                + ".",
                facts=srcs,
                cites=tuple(r.cite for r in rows),
            )
        )
    return mapped, steps, used, caps
