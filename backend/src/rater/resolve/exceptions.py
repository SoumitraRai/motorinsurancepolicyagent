"""Footnotes, notes and T&C lines, applied before the answer.

Spec SR18, SR19; intent NN2, D2; spec C2, C5.
"""

import math
from dataclasses import dataclass, field
from decimal import Decimal

from rater.facts import Facts
from rater.grids.bands import Band
from rater.grids.model import ExceptionRule, Grid, describe, dim_matches
from rater.resolve.common import Refusal, Step
from rater.resolve.mapping import dim_value
from rater.switches import Switches

BROKER_WHY = "depends on broker volume, which the policy can't show"


@dataclass
class Applied:
    rates: dict[str, Decimal]
    steps: list[Step] = field(default_factory=list)
    not_applied: list[ExceptionRule] = field(default_factory=list)
    used: set[str] = field(default_factory=set)


def _holds(
    rule: ExceptionRule, facts: Facts, grid: Grid, mapped: dict[str, str]
) -> bool | str | tuple[str, ...]:
    """True; False (a policy fact rules it out); "elsewhere" (scoped to another zone/cluster/region);
    or the facts that are missing to decide."""
    missing: list[str] = []
    for dim, want in rule.when:
        if dim in mapped and not dim_matches(want, mapped[dim]):
            return "elsewhere"
    for dim, want in rule.when:
        if isinstance(want, Band) and math.isinf(want.lo) and math.isinf(want.hi):
            continue  # "All": always holds
        have, srcs = dim_value(dim, facts, grid, mapped)
        if have is None:
            missing.extend(srcs or (dim,))
        elif not dim_matches(want, have):
            return False
    return tuple(missing) if missing else True


def _condition(rule: ExceptionRule) -> str:
    return " and ".join(f"{d} {describe(w)}" for d, w in rule.when) or "all policies"


def apply_exceptions(
    rates: dict[str, Decimal], facts: Facts, grid: Grid, mapped: dict[str, str], switches: Switches
) -> Applied | Refusal:
    out = Applied(rates=dict(rates))
    for rule in grid.exceptions:
        if rule.kind == "broker_side":
            if switches.broker_eligibility == "require_evidence":
                return Refusal(
                    "unsupported",
                    "Eligibility depends on the broker's business, which the policy "
                    "can't show (BROKER_ELIGIBILITY=require_evidence).",
                    cites=(rule.cite,),
                )
            out.not_applied.append(rule)
            out.steps.append(
                Step(
                    "broker_bonus", f"Possible, not applied: {rule.text} ({BROKER_WHY}).", cites=(rule.cite,)
                )
            )
            continue
        if rule.kind in ("out_of_scope", "definition", "basis", "slab_basis", "post_issue", "process"):
            out.steps.append(
                Step("note", f"Grid note ({rule.kind.replace('_', ' ')}): {rule.text}", cites=(rule.cite,))
            )
            continue
        if rule.kind == "unclassified":
            return Refusal(
                "ambiguous",
                f'A grid term in scope could not be interpreted: "{rule.text}".',
                cites=(rule.cite,),
            )

        holds = _holds(rule, facts, grid, mapped)
        if holds == "elsewhere":
            continue
        if isinstance(holds, tuple):
            return Refusal(
                "ambiguous",
                f'Whether "{rule.text}" applies depends on {", ".join(holds)}, '
                "which could not be read from the policy.",
                cites=(rule.cite,),
                missing=holds,
            )
        if not holds:
            out.steps.append(
                Step(
                    "exception",
                    f'"{rule.text}" does not apply ({_condition(rule)} not met).',
                    cites=(rule.cite,),
                )
            )
            continue
        out.used.update(n for d, _ in rule.when for n in dim_value(d, facts, grid, mapped)[1])

        if rule.kind == "undefined_decline":
            return Refusal(
                "ambiguous",
                f'The grid declines some RTOs without naming them: "{rule.text}". '
                "This policy falls in that scope.",
                cites=(rule.cite,),
            )
        if rule.effect == "decline":
            return Refusal(
                "unsupported", f'The grid declines this policy: "{rule.text}".', cites=(rule.cite,)
            )

        pct = Decimal(str(rule.percent or 0))
        changed = []
        for comp in rule.components:
            if comp not in out.rates:
                continue
            before = out.rates[comp]
            if rule.effect == "reduce":
                after = (
                    before - pct if switches.lesser_percent_means == "points" else before * (1 - pct / 100)
                )
            elif rule.effect == "add":
                after = before + pct
            elif rule.effect == "flat":
                after = pct
            else:
                continue
            out.rates[comp] = after
            changed.append(f"{comp.upper()} {before.normalize():f}% → {after.normalize():f}%")
        how = (
            " (percentage points)"
            if rule.effect == "reduce" and switches.lesser_percent_means == "points"
            else ""
        )
        out.steps.append(
            Step(
                "exception",
                f'"{rule.text}" applies: {", ".join(changed) or "no rate affected"}{how}.',
                cites=(rule.cite,),
            )
        )
    return out
