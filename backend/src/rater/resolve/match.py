"""Row matching (spec SR17): every dimension a row uses must match; unknowns and band gaps never guess."""

import math
from dataclasses import dataclass

from rater.facts import Facts
from rater.grids.bands import Band
from rater.grids.model import Grid, RateCell, RateRule, describe, dim_matches
from rater.resolve.common import Refusal
from rater.resolve.mapping import dim_value


@dataclass(frozen=True)
class Match:
    cell: RateCell
    rules: tuple[RateRule, ...]
    used: frozenset[str]


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
    relevant = [r for r in grid.rules if getattr(r, component) is not None]
    if not relevant:
        return None

    matched: list[RateRule] = []
    undetermined: list[tuple[RateRule, set[str]]] = []
    near: list[tuple[RateRule, str, float]] = []  # rows failing only on one band dimension
    used: set[str] = set()
    for rule in relevant:
        missing: set[str] = set()
        failed: list[tuple[str, float | None]] = []
        for dim, want in rule.dims:
            have, srcs = dim_value(dim, facts, grid, mapped)
            if have is None:
                missing.update(srcs or (dim,))
            elif not dim_matches(want, have):
                failed.append((dim, float(have) if isinstance(want, Band) else None))
            else:
                used.update(srcs)
        if not failed and missing:
            undetermined.append((rule, missing))
        elif not failed:
            matched.append(rule)
        elif len(failed) == 1 and failed[0][1] is not None and not missing:
            near.append((rule, failed[0][0], failed[0][1]))

    def pct(r: RateRule) -> float:
        cell = getattr(r, component)
        return float(cell.percent)

    if undetermined:
        known = {pct(r) for r in matched}
        if not matched or any(pct(r) not in known for r, _ in undetermined):
            names = sorted({n for _, m in undetermined for n in m})
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
