"""Row matching (spec SR17): every dimension a row uses must match; unknowns and band gaps never guess."""

import math
from dataclasses import dataclass

from rater.facts import Facts, Fuel
from rater.grids.bands import Band
from rater.grids.model import Grid, RateCell, RateRule, describe, dim_matches
from rater.resolve.common import Refusal
from rater.resolve.mapping import dim_value


@dataclass(frozen=True)
class Match:
    cell: RateCell
    rules: tuple[RateRule, ...]
    used: frozenset[str]
    unneeded: tuple[str, ...] = ()  # unknown facts that every possible value maps to the same rate


# Facts with a closed set of values. Only for these can "every value gives the same rate" be checked.
DOMAINS: dict[str, frozenset[str]] = {
    "fuel": frozenset(f.value for f in Fuel),
    "ncb_flag": frozenset({"ncb", "no_ncb"}),
    "has_add_ons": frozenset({"yes", "no"}),
    "cpa_cover": frozenset({"yes", "no"}),
    "business_type": frozenset({"new", "renewal", "rollover"}),
    "tw_type": frozenset({"scooter", "motorcycle", "moped"}),
}


def _irrelevant(
    undetermined: list[tuple[RateRule, set[str], set[str]]], component: str
) -> tuple[str, ...] | None:
    """The missing dims, if all their possible values are covered and every candidate row has one rate."""
    dims = {frozenset(d) for _, _, d in undetermined}
    if len(dims) != 1:
        return None
    (missing,) = dims
    if not missing or not missing <= set(DOMAINS):
        return None
    if len({float(getattr(r, component).percent) for r, _, _ in undetermined}) != 1:
        return None
    for dim in missing:
        covered: set[str] = set()
        for rule, _, _ in undetermined:
            want = dict(rule.dims)[dim]
            if isinstance(want, frozenset):
                covered |= {str(v).lower() for v in want}
            elif isinstance(want, str):
                covered.add(want.lower())
            else:
                return None
        if not DOMAINS[dim] <= covered:
            return None
    return tuple(sorted(missing))


def _in_gap(rules: list[RateRule], dim: str, value: float) -> bool:
    bands = [w for r in rules for d, w in r.dims if d == dim and isinstance(w, Band)]
    if not bands:
        return False
    lo = min(b.lo for b in bands)
    hi = max(b.hi for b in bands)
    inside_span = (lo < value < hi) or math.isinf(lo) or math.isinf(hi)
    return inside_span and not any(b.contains(value) for b in bands)


def match_component(
    component: str, facts: Facts, grid: Grid, mapped: dict[str, str]
) -> Match | Refusal | None:
    """The rate for one component (`od`/`tp`), a refusal, or None when the grid has no rows for it."""
    pt = facts.value("policy_type")
    relevant = [
        r
        for r in grid.rules
        if getattr(r, component) is not None
        and ("policy_type" not in r.dim_map or pt is None or dim_matches(r.dim_map["policy_type"], pt))
    ]
    if not relevant:
        return None

    matched: list[RateRule] = []
    undetermined: list[tuple[RateRule, set[str], set[str]]] = []
    near: list[tuple[RateRule, str, float]] = []  # rows failing only on one band dimension
    used: set[str] = set()
    for rule in relevant:
        missing: set[str] = set()
        missing_dims: set[str] = set()
        failed: list[tuple[str, float | None]] = []
        for dim, want in rule.dims:
            if isinstance(want, Band) and math.isinf(want.lo) and math.isinf(want.hi):
                continue  # "All": no constraint, so the fact is not needed
            have, srcs = dim_value(dim, facts, grid, mapped)
            if have is None:
                missing.update(srcs or (dim,))
                missing_dims.add(dim)
            elif not dim_matches(want, have):
                failed.append((dim, float(have) if isinstance(want, Band) else None))
            else:
                used.update(srcs)
        if not failed and missing:
            undetermined.append((rule, missing, missing_dims))
        elif not failed:
            matched.append(rule)
        elif len(failed) == 1 and failed[0][1] is not None and not missing:
            near.append((rule, failed[0][0], failed[0][1]))

    def pct(r: RateRule) -> float:
        cell = getattr(r, component)
        return float(cell.percent)

    if undetermined and not matched:
        unneeded = _irrelevant(undetermined, component)
        if unneeded is not None:
            rows = tuple(r for r, _, _ in undetermined)
            return Match(
                cell=getattr(rows[0], component), rules=rows, used=frozenset(used), unneeded=unneeded
            )
    if undetermined:
        known = {pct(r) for r in matched}
        if not matched or any(pct(r) not in known for r, _, _ in undetermined):
            names = sorted({n for _, m, _ in undetermined for n in m})
            return Refusal(
                "ambiguous",
                f"The {component.upper()} rate depends on {', '.join(names)}, "
                "which could not be read from the policy.",
                missing=tuple(names),
            )

    if matched:
        distinct = sorted({pct(r) for r in matched})
        if len(distinct) > 1:
            return Refusal(
                "ambiguous",
                f"More than one {component.upper()} rate applies ({', '.join(f'{p:g}%' for p in distinct)}); "
                "the grid contradicts itself for this policy.",
                cites=tuple(getattr(r, component).cite for r in matched),
            )
        return Match(cell=getattr(matched[0], component), rules=tuple(matched), used=frozenset(used))

    for rule, dim, value in near:
        # Only rows that agree with the policy on every other dimension say where this band's edges are.
        if _in_gap([r for r, d, _ in near if d == dim], dim, value):
            labels = sorted({describe(w) for r, d2, _ in near if d2 == dim for d, w in r.dims if d == dim})
            return Refusal(
                "ambiguous",
                f"The policy's {dim} ({value:g}) falls between the grid's published bands "
                f"({', '.join(labels)}).",
                cites=(rule.cite,),
            )
    return Refusal(
        "unsupported", f"No row in '{grid.title}' matches this policy for the {component.upper()} rate."
    )
