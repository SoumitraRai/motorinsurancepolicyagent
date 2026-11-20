"""Grid effective-date check (intent D1, spec SR20; switch GRID_DATE_POLICY)."""

from datetime import date
from typing import Any

from rater.facts import Facts
from rater.grids.model import Grid
from rater.resolve.common import Refusal, Step
from rater.switches import Switches


def _as_date(value: Any) -> date | None:
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None
    return None


def check_dates(facts: Facts, grid: Grid, switches: Switches) -> tuple[Step, bool] | Refusal:
    """A trace step plus whether it raised a confidence-lowering warning, or a refusal."""
    if grid.effective_from is None and grid.effective_to is None:
        return Step("date", f"Grid '{grid.title}': effective period not stated."), False

    stated = grid.date_text or (f"{grid.effective_from or '…'} to {grid.effective_to or '…'}")
    cites = (grid.date_cite,) if grid.date_cite else ()
    start = _as_date(facts.value("policy_start_date")) or _as_date(facts.value("issue_date"))
    used = ("policy_start_date",)
    if start is None:
        if switches.grid_date_policy == "strict":
            return Refusal(
                "ambiguous",
                "The policy date could not be read, so the grid's effective period "
                f"({stated}) cannot be checked.",
                cites=cites,
                missing=used,
            )
        step = Step(
            "date",
            f"Grid effective {stated}; the policy date could not be read.",
            cites=cites,
            warnings=[f"grid effective {stated}; policy date unknown; a newer grid may exist"],
        )
        return step, True

    if grid.effective_to is not None and start > grid.effective_to:
        return Refusal(
            "unsupported",
            f"The policy is dated {start.isoformat()}, after the grid's stated end ({stated}).",
            cites=cites,
        )
    if grid.effective_from is not None and start < grid.effective_from:
        warning = f"grid effective {stated}; policy dated {start.isoformat()}; a newer grid may exist"
        if switches.grid_date_policy == "strict":
            return Refusal(
                "unsupported",
                f"The policy is dated {start.isoformat()}, outside the grid's effective period ({stated}).",
                cites=cites,
            )
        return Step(
            "date",
            f"Grid effective {stated}; policy dated {start.isoformat()}.",
            facts=used,
            cites=cites,
            warnings=[warning],
        ), True
    return Step(
        "date",
        f"Policy dated {start.isoformat()} is within the grid's effective period ({stated}).",
        facts=used,
        cites=cites,
    ), False
