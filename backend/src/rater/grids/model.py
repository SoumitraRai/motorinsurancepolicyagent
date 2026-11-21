"""The common rule model every grid adapter produces (spec Design > Common rule model).

Every rate, mapping row and exception keeps the citation of the cell or PDF row it came from, and the
raw value read there, so any result can be re-checked against the original file (AC2).
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from rater.citations import GridCite
from rater.grids.bands import Band
from rater.resolve.confidence import Cap


@dataclass(frozen=True)
class NotIn:
    """Any value except those listed (e.g. Go Digit's "Others" makes)."""

    values: frozenset[str]


# A rule dimension is an exact value, any of a set of values, "anything but", or a numeric band.
DimValue = str | frozenset[str] | NotIn | Band


def norm_key(text: str) -> str:
    return "".join(ch for ch in str(text).upper() if ch.isalnum())


def dim_matches(want: DimValue, have: Any) -> bool:
    if isinstance(have, list | tuple):  # list-valued fact (e.g. add-on covers): any keyword in any item
        words = (
            want.values if isinstance(want, NotIn) else want if isinstance(want, frozenset) else {str(want)}
        )
        hit = any(norm_key(w) in norm_key(item) for item in have for w in words)
        return not hit if isinstance(want, NotIn) else hit
    if isinstance(want, Band):
        return isinstance(have, int | float) and not isinstance(have, bool) and want.contains(float(have))
    if isinstance(want, NotIn):
        return norm_key(have) not in {norm_key(v) for v in want.values}
    if isinstance(want, frozenset):
        return norm_key(have) in {norm_key(v) for v in want}
    return norm_key(have) == norm_key(want)


def describe(want: DimValue) -> str:
    if isinstance(want, Band):
        return want.label
    if isinstance(want, NotIn):
        return "not " + " / ".join(sorted(want.values))
    if isinstance(want, frozenset):
        return " / ".join(sorted(want))
    return want


@dataclass(frozen=True)
class RateCell:
    percent: float
    raw: Any
    cite: GridCite
    label: str = ""  # e.g. "Max CD2" (spec C7)


@dataclass(frozen=True)
class RateRule:
    dims: tuple[tuple[str, DimValue], ...]
    od: RateCell | None
    tp: RateCell | None
    cite: GridCite  # the whole row (or row range) the rule was read from
    label: str = ""  # human description of the row, e.g. "Zone 2 · Package · Petrol · >10-50k"

    @property
    def dim_map(self) -> Mapping[str, DimValue]:
        return dict(self.dims)


@dataclass(frozen=True)
class MappingRow:
    key: str
    value: str
    cite: GridCite
    raw: Any = None
    note: str = ""  # how the row was derived, shown in the trace (e.g. "via the city → state list")
    cap: Cap | None = None  # confidence cap when the row rests on a documented assumption


@dataclass(frozen=True)
class MappingTable:
    """Maps one policy dimension (e.g. `rto`) to a grid dimension (e.g. `cluster`)."""

    name: str
    source: str
    target: str
    rows: tuple[MappingRow, ...]
    # What an absent source fact means: usually "ambiguous" (could not read it); "unsupported" when the grid
    # itself lacks the table that would let any policy supply it (spec C8).
    if_missing: str = "ambiguous"
    missing_reason: str = ""

    def lookup(self, key: str) -> list[MappingRow]:
        k = norm_key(key)
        return [r for r in self.rows if norm_key(r.key) == k]


@dataclass(frozen=True)
class CitySplitTable:
    """State → zone, where some states are split by city.

    Keys: `STATE` (whole state), `STATE|CITY` (a named city), `STATE|*` ("Rest of" the state).
    """

    name: str
    target: str
    rows: tuple[MappingRow, ...]
    source: str = "rto"


@dataclass(frozen=True)
class RtoRegionTable:
    """RTO code → grid region, from the grid's own RTO list; codes it doesn't list fall back to the RTO's
    state (two-letter prefix) and the grid's state-level rows."""

    name: str
    target: str
    by_code: tuple[MappingRow, ...]
    by_state: tuple[MappingRow, ...]
    source: str = "rto"


@dataclass(frozen=True)
class ExceptionRule:
    kind: str  # see rater.grids.textrules
    text: str
    cite: GridCite
    effect: str | None = None  # reduce | add | flat | decline
    percent: float | None = None
    when: tuple[tuple[str, DimValue], ...] = ()  # all must hold for the rule to apply; () = always
    components: tuple[str, ...] = ("od", "tp")


@dataclass(frozen=True)
class Unpublished:
    """A component the grid publishes no rate for, for a policy type (spec C3)."""

    policy_type: str
    component: str
    reason: str
    cite: GridCite


@dataclass(frozen=True)
class Grid:
    id: str
    insurer: str
    file: str
    title: str
    vehicle_classes: frozenset[str]
    policy_types: frozenset[str]
    rules: tuple[RateRule, ...]
    business_types: frozenset[str] | None = None  # None: the grid does not split on business type
    mappings: tuple[MappingTable | CitySplitTable | RtoRegionTable, ...] = ()
    exceptions: tuple[ExceptionRule, ...] = ()
    unpublished: tuple[Unpublished, ...] = ()
    effective_from: date | None = None
    effective_to: date | None = None
    date_text: str | None = None
    date_cite: GridCite | None = None
    caps: tuple[Cap, ...] = ()
    new_business_counts_as_ncb: bool = False
    notes: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class GridSet:
    grids: tuple[Grid, ...]
    # Canonical insurer name -> lowercase substrings that identify it in a policy's insurer text.
    aliases: Mapping[str, tuple[str, ...]]
