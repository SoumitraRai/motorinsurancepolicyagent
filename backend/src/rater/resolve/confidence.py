"""Confidence rules (spec SR23).

Per fact: `high` when its quote is in the PDF's text layer, or both OCR engines read the same value
independently (`confirmed_both`; PO 2026-11-23, C4 amended); `medium` when both engines contain the quote;
`low` when only one engine or neither does; `unknown` when absent.

Overall (PO 2026-11-23): the share of facts the result depended on that are `high`. At least 90% gives
`high`, at least 70% `medium`, less `low`; never below the weakest fact's level. A fact that picked the
rate row (mapping, row match, T&C condition) and is below `medium` makes the result `low` whatever the
share. Then one level lower per date warning (D1) and capped by any named assumption (e.g. C1).
Resolution itself is all-or-nothing, so it never adds doubt.
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rater.facts import Fact, Level

ORDER: list["Level"] = ["unknown", "low", "medium", "high"]
HIGH_SHARE = 0.9
MEDIUM_SHARE = 0.7
_BY_VERIFICATION: dict[str, "Level"] = {
    "text_layer": "high",
    "confirmed_both": "high",
    "verified_both": "medium",
    "reviewer_supplied": "medium",
    "derived": "medium",
    "verified_one": "low",
    "unverified": "low",
    "not_found": "unknown",
}


@dataclass(frozen=True)
class Cap:
    level: "Level"
    reason: str


@dataclass(frozen=True)
class Confidence:
    level: "Level"
    reason: str
    capped_by: list[str] = field(default_factory=list)


def fact_level(fact: "Fact") -> "Level":
    if fact.value is None:
        return "unknown"
    return _BY_VERIFICATION.get(fact.verification, "low")


def _lower(a: "Level", b: "Level") -> "Level":
    return a if ORDER.index(a) <= ORDER.index(b) else b


def _higher(a: "Level", b: "Level") -> "Level":
    return a if ORDER.index(a) >= ORDER.index(b) else b


def _where(name: str, fact: "Fact") -> str:
    page = f", page {fact.page}" if fact.page else ""
    return f"{name} ({fact.verification.replace('_', ' ')}{page})"


def overall(
    used: dict[str, "Fact"],
    warnings: int,
    caps: list[Cap] | None = None,
    row: set[str] | frozenset[str] = frozenset(),
) -> Confidence:
    if not used:
        return Confidence("low", "no policy facts supported this result")
    levels = {n: fact_level(f) for n, f in used.items()}
    confirmed = sum(1 for lv in levels.values() if lv == "high")
    share = confirmed / len(used)
    by_share: Level = "high" if share >= HIGH_SHARE else "medium" if share >= MEDIUM_SHARE else "low"
    name, weakest = min(used.items(), key=lambda kv: (ORDER.index(levels[kv[0]]), kv[0]))
    level = _higher(by_share, levels[name] if levels[name] != "unknown" else "low")
    reason = f"{confirmed} of {len(used)} facts the result used confirmed ({share:.0%})"
    weak_rows = sorted(n for n in row if n in levels and ORDER.index(levels[n]) < ORDER.index("medium"))
    if weak_rows:
        level = "low"
        reason += "; a fact that picked the rate row is weak: " + _where(weak_rows[0], used[weak_rows[0]])
    elif levels[name] != "high":
        reason += "; weakest link: " + _where(name, weakest)

    for _ in range(warnings):
        level = _lower(level, ORDER[max(ORDER.index(level) - 1, 1)])
    if warnings:
        reason += f"; lowered for {warnings} date warning{'s' if warnings > 1 else ''}"

    capped: list[str] = []
    for cap in caps or []:
        if ORDER.index(cap.level) < ORDER.index(level):
            level = cap.level
        capped.append(cap.reason)
    if capped:
        reason += "; capped by " + "; ".join(capped)
    return Confidence(level, reason, capped)
