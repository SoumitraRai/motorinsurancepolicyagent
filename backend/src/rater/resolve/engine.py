"""Deterministic resolution (intent NN1, NN2; spec SR15–SR23). Pure: no I/O, no clock, no randomness.

select grid → check dates → map facts into grid vocabulary → match the row for each applicable
component → apply exceptions → assemble the result with citations and confidence. Any step may refuse;
a refusal is final and carries its evidence.
"""

from decimal import Decimal
from typing import Any

from rater.citations import PolicyCite
from rater.facts import Fact, Facts
from rater.grids.model import Grid, GridSet, RateCell, describe, dim_matches
from rater.resolve.common import Refusal, Step
from rater.resolve.confidence import Cap, overall
from rater.resolve.dates import check_dates
from rater.resolve.exceptions import BROKER_WHY, apply_exceptions
from rater.resolve.mapping import apply_mappings, dim_value
from rater.resolve.match import Match, match_component
from rater.resolve.select import select_grid
from rater.result import ConfidenceOut, NotApplied, RateOut, Result, TraceStep
from rater.switches import Switches

ENGINE_VERSION = "0.1.0"
NOT_APPLICABLE = {
    "od": "Stand-alone TP policy: OD not applicable",
    "tp": "Stand-alone OD policy: TP not applicable",
}


def _applicability(policy_type: Any) -> dict[str, bool] | None:
    return (
        {
            "comprehensive": {"od": True, "tp": True},
            "satp": {"od": False, "tp": True},
            "saod": {"od": True, "tp": False},
        }.get(str(policy_type))
        if policy_type is not None
        else None
    )


def _rate_reason(cell: RateCell) -> str:
    if cell.label.lower().startswith("max"):
        return f"insurer's published maximum ({cell.label})"
    return cell.label


class _Run:
    def __init__(self, facts: Facts, gridset: GridSet, switches: Switches, policy_file: str) -> None:
        self.facts = facts
        self.gridset = gridset
        self.switches = switches
        self.policy_file = policy_file
        self.steps: list[Step] = []
        self.used: set[str] = set()
        self.row_used: set[str] = set()  # facts that picked the rate row (mapping, match, T&C conditions)
        self.warnings = 0
        self.grid: Grid | None = None
        self.caps: list[Cap] = []
        # An unknown policy date (strict mode) is held back: it decides the answer only if nothing else
        # makes the policy unsupported (Vaatun 2026-11-22: ambiguous only when it would change the result).
        self.pending: Refusal | None = None

    # -- trace ------------------------------------------------------------------------------------
    def _policy_cite(self, names: tuple[str, ...]) -> tuple[str | None, list[dict[str, Any]]]:
        first: str | None = None
        dicts: list[dict[str, Any]] = []
        for n in names:
            f = self.facts.get(n)
            if f.page is None:
                continue
            cite = PolicyCite(self.policy_file, f.page)
            text = f.policy_citation or cite.render()
            first = first or text
            dicts.append(cite.to_dict())
        return first, dicts

    def _trace(self) -> list[TraceStep]:
        out = []
        for i, s in enumerate(self.steps, start=1):
            policy, policy_dicts = self._policy_cite(s.facts)
            out.append(
                TraceStep(
                    step=i,
                    kind=s.kind,
                    decision=s.decision,
                    policy_citation=policy,
                    grid_citation="; ".join(c.render() for c in s.cites) or None,
                    citations=policy_dicts + [c.to_dict() for c in s.cites],
                    warnings=s.warnings,
                )
            )
        return out

    def _meta(self) -> dict[str, Any]:
        return {
            "engine": ENGINE_VERSION,
            "grid": self.grid.id if self.grid else None,
            "switches": self.switches.as_dict(),
        }

    # -- outcomes ---------------------------------------------------------------------------------
    def refuse(self, r: Refusal) -> Result:
        if self.pending is not None and r is not self.pending and r.status != "unsupported":
            r = Refusal(
                r.status,
                f"{r.reason} Also: {self.pending.reason}",
                cites=r.cites + self.pending.cites,
                missing=tuple(dict.fromkeys(r.missing + self.pending.missing)),
            )
        self.steps.append(Step("result", r.reason, cites=r.cites))
        applicable = _applicability(self.facts.value("policy_type"))
        rates = {}
        for comp in ("od", "tp"):
            if applicable is None:
                rates[comp] = RateOut(applicable=None, rate_percent=None, reason="policy type unknown")
            elif not applicable[comp]:
                rates[comp] = RateOut.not_applicable(NOT_APPLICABLE[comp])
            else:
                rates[comp] = RateOut(applicable=True, rate_percent=None, reason=r.reason)
        used = {n: self.facts.get(n) for n in sorted(self.used | set(r.missing))}
        conf = overall(
            used, self.warnings, (list(self.grid.caps) if self.grid else []) + self.caps, row=self.row_used
        )
        return Result(
            status=r.status,
            facts=self.facts,
            rates=rates,
            trace=self._trace(),
            confidence=ConfidenceOut(level=conf.level, reason=conf.reason, capped_by=conf.capped_by),
            clarification={"facts": sorted(set(r.missing))}
            if r.status == "ambiguous" and r.missing
            else None,
            meta=self._meta(),
        )

    def _explain(self, refusal: Refusal, grid: Grid, mapped: dict[str, str]) -> Refusal:
        """For "no row matches", prefer a decline / no-rate note covering this policy, with its citation.
        A term that can't be interpreted and covers the policy makes the answer ambiguous instead."""
        if refusal.status != "unsupported" or not refusal.reason.startswith("No row"):
            return refusal
        for rule in grid.exceptions:
            if rule.kind not in ("unclassified", "catch_all") or not rule.when:
                continue
            if all(
                (v := dim_value(d, self.facts, grid, mapped)[0]) is not None and dim_matches(w, v)
                for d, w in rule.when
            ):
                return Refusal(
                    "ambiguous",
                    f"No row gives a defined rate; a grid term covering this policy could not be "
                    f'interpreted: "{rule.text}".',
                    cites=(rule.cite,),
                )
        for rule in grid.exceptions:
            if rule.effect != "decline":
                continue
            if all(
                dim_matches(w, v)
                for d, w in rule.when
                if (v := dim_value(d, self.facts, grid, mapped)[0]) is not None
            ) and all(dim_value(d, self.facts, grid, mapped)[0] is not None for d, _ in rule.when):
                return Refusal(
                    "unsupported",
                    f'The grid declines this policy or gives no rate: "{rule.text}".',
                    cites=(rule.cite,),
                )
        return refusal

    def run(self) -> Result:
        sel = select_grid(self.facts, self.gridset)
        if isinstance(sel, Refusal):
            return self.refuse(sel)
        grid = self.grid = sel.grid
        self.steps.extend(sel.steps)
        self.used.update(sel.used)
        applicable = _applicability(self.facts.value("policy_type"))
        assert applicable is not None  # selection requires a known policy type

        dated = check_dates(self.facts, grid, self.switches)
        if isinstance(dated, Refusal) and dated.status == "ambiguous":
            self.pending = dated
            self.steps.append(Step("date", dated.reason, cites=dated.cites))
        elif isinstance(dated, Refusal):
            return self.refuse(dated)
        else:
            step, warned = dated
            self.steps.append(step)
            self.warnings += int(warned)
            self.used.update(step.facts)

        mapped_out = apply_mappings(self.facts, grid)
        if isinstance(mapped_out, Refusal):
            return self.refuse(mapped_out)
        mapped, map_steps, map_used, map_caps = mapped_out
        self.steps.extend(map_steps)
        self.used.update(map_used)
        self.row_used.update(map_used)
        self.caps.extend(map_caps)

        matches: dict[str, Match] = {}
        outs: dict[str, RateOut] = {}
        pt = str(self.facts.value("policy_type"))
        for comp in ("od", "tp"):
            if not applicable[comp]:
                outs[comp] = RateOut.not_applicable(NOT_APPLICABLE[comp])
                continue
            m = match_component(comp, self.facts, grid, mapped)
            if m is None:
                stated = next(
                    (u for u in grid.unpublished if u.policy_type == pt and u.component == comp), None
                )
                if stated is None:
                    return self.refuse(
                        Refusal(
                            "unsupported",
                            f"The grid '{grid.title}' publishes no {comp.upper()} rate for {pt} policies.",
                        )
                    )
                outs[comp] = RateOut(
                    applicable=True,
                    rate_percent=None,
                    reason=stated.reason,
                    grid_citation=stated.cite.render(),
                    citations=[stated.cite.to_dict()],
                )
                self.steps.append(Step("match", f"{comp.upper()}: {stated.reason}.", cites=(stated.cite,)))
                continue
            if isinstance(m, Refusal):
                return self.refuse(self._explain(m, grid, mapped))
            matches[comp] = m
            self.used.update(m.used)
            self.row_used.update(m.used)
            rule = m.rules[0]
            what = rule.label or ", ".join(f"{d} {describe(w)}" for d, w in rule.dims)
            note = f" ({_rate_reason(m.cell)})" if m.cell.label else ""
            if m.unneeded:
                note += (
                    f"; {', '.join(m.unneeded)} not read from the policy, but every value the grid lists "
                    "gives the same rate"
                )
            self.steps.append(
                Step(
                    "match",
                    f"{comp.upper()} row matched ({what}): {m.cell.percent:g}%{note}.",
                    facts=tuple(sorted(m.used)),
                    cites=tuple(getattr(r, comp).cite for r in m.rules),
                )
            )

        if not matches:
            return self.refuse(
                Refusal(
                    "unsupported",
                    f"The grid '{grid.title}' publishes no rate for any applicable component of this policy.",
                )
            )

        rates = {c: Decimal(str(m.cell.percent)) for c, m in matches.items()}
        applied = apply_exceptions(rates, self.facts, grid, mapped, self.switches)
        if isinstance(applied, Refusal):
            return self.refuse(applied)
        self.steps.extend(applied.steps)
        self.used.update(applied.used)
        self.row_used.update(applied.used)
        if self.pending is not None:
            return self.refuse(self.pending)

        for comp, m in matches.items():
            final = applied.rates[comp]
            outs[comp] = RateOut(
                applicable=True,
                rate_percent=float(final),
                reason=_rate_reason(m.cell),
                raw_cell_value=str(m.cell.raw),
                grid_citation=m.cell.cite.render(),
                citations=[m.cell.cite.to_dict()],
            )
        summary = "; ".join(
            f"{c.upper()} "
            + (
                "not applicable"
                if o.applicable is False
                else "not published"
                if o.rate_percent is None
                else f"{o.rate_percent:g}%"
            )
            for c, o in outs.items()
        )
        self.steps.append(
            Step("result", f"Resolved: {summary}.", cites=tuple(m.cell.cite for m in matches.values()))
        )

        conf = overall(
            {n: self.facts.get(n) for n in sorted(self.used)},
            self.warnings,
            list(grid.caps) + self.caps,
            row=self.row_used,
        )
        return Result(
            status="resolved",
            facts=self.facts,
            rates=outs,
            trace=self._trace(),
            confidence=ConfidenceOut(level=conf.level, reason=conf.reason, capped_by=conf.capped_by),
            not_applied=[
                NotApplied(rule=r.text, why=BROKER_WHY, grid_citation=r.cite.render())
                for r in applied.not_applied
            ],
            meta=self._meta(),
        )


BUSINESS_TYPES = ("new", "renewal", "rollover")


def _rate_key(result: Result) -> tuple[tuple[str, Any, Any], ...]:
    return tuple((c, o.applicable, o.rate_percent) for c, o in sorted(result.rates.items()))


def resolve(facts: Facts, gridset: GridSet, switches: Switches, policy_file: str) -> Result:
    result = _Run(facts, gridset, switches, policy_file).run()
    missing = (result.clarification or {}).get("facts")
    if result.status != "ambiguous" or missing != ["business_type"]:
        return result
    if facts.value("business_type") is not None:
        return result
    # Vaatun 2026-11-22: "ambiguous" only when the missing fact would change the rate. Try every business
    # type; if each one resolves to the same rates, the business type doesn't matter for this policy.
    tries = []
    for bt in BUSINESS_TYPES:
        assumed = facts.model_copy(deep=True)
        assumed.business_type = Fact(
            value=bt, verification="derived", note="assumed to test whether it changes the rate"
        )
        tries.append(_Run(assumed, gridset, switches, policy_file).run())
    if not all(t.status == "resolved" for t in tries) or len({_rate_key(t) for t in tries}) != 1:
        return result
    out = tries[0]
    note = TraceStep(
        step=0,
        kind="business_type",
        decision="The business type (new, renewal or rollover) could not be established from the policy, "
        "but every business type gives the same rates, so it does not change the answer. The steps below "
        f"use '{BUSINESS_TYPES[0]}'.",
    )
    out.trace = [t.model_copy(update={"step": i}) for i, t in enumerate([note, *out.trace], start=1)]
    out.facts = facts
    return out
