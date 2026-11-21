"""Grid selection (spec SR15): insurer → vehicle class → policy type → business type where the grid splits."""

from dataclasses import dataclass

from rater import insurers
from rater.facts import Facts
from rater.grids.model import Grid, GridSet
from rater.resolve.common import Refusal, Step


@dataclass(frozen=True)
class Selection:
    grid: Grid
    insurer: str
    used: tuple[str, ...]
    steps: tuple[Step, ...]


def canonical_insurer(text: str, gridset: GridSet) -> str | None:
    return insurers.canonical(text, dict(gridset.aliases))


def select_grid(facts: Facts, gridset: GridSet) -> Selection | Refusal:
    insurer_text = facts.value("insurer")
    if insurer_text is None:
        return Refusal("ambiguous", "The insurer could not be read from the policy.", missing=("insurer",))
    insurer = canonical_insurer(insurer_text, gridset)
    supported = ", ".join(sorted(gridset.aliases))
    if insurer is None:
        return Refusal(
            "unsupported", f"No grid was supplied for the insurer '{insurer_text}'. Supported: {supported}."
        )

    vc, pt = facts.value("vehicle_class"), facts.value("policy_type")
    missing = tuple(n for n, v in (("vehicle_class", vc), ("policy_type", pt)) if v is None)
    if missing:
        return Refusal(
            "ambiguous",
            "The vehicle class or policy type could not be read from the policy.",
            missing=missing,
        )

    insurer_grids = [g for g in gridset.grids if g.insurer == insurer]
    cands = [g for g in insurer_grids if vc in g.vehicle_classes and pt in g.policy_types]
    if not cands:
        searched = "; ".join(sorted(g.title for g in insurer_grids)) or "none"
        return Refusal(
            "unsupported",
            f"No {insurer} grid covers {vc} {pt} policies (grids searched: {searched}).",
        )

    used = ["insurer", "vehicle_class", "policy_type"]
    splits = [g for g in cands if g.business_types is not None]
    if splits:
        bt = facts.value("business_type")
        if bt is None:
            return Refusal(
                "ambiguous",
                f"The {insurer} grid depends on business type (new, renewal or rollover), "
                "which could not be established from the policy.",
                missing=("business_type",),
            )
        used.append("business_type")
        cands = [g for g in cands if g.business_types is None or bt in g.business_types]
        if not cands:
            return Refusal("unsupported", f"No {insurer} grid covers {bt} business for {vc} {pt} policies.")

    if len(cands) > 1:
        return Refusal("ambiguous", "More than one grid applies: " + "; ".join(g.title for g in cands) + ".")

    grid = cands[0]
    step = Step(
        "select",
        f"Insurer {insurer}, {vc.replace('_', ' ')}, {pt} policy: using the grid '{grid.title}'.",
        facts=tuple(used),
    )
    return Selection(grid=grid, insurer=insurer, used=tuple(used), steps=(step,))
