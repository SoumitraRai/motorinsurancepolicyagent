"""Confidence rules (spec SR23).

Per fact: `high` when its quote is in the PDF's text layer, `medium` when both OCR engines contain it
(the cap for OCR-read facts, B3), `low` when only one engine or neither does, `unknown` when absent.
Overall: the weakest fact the result depended on, one level lower per date warning (D1), then capped
by any named assumption (e.g. C1). Resolution itself is all-or-nothing, so it never adds doubt.
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rater.facts import Fact, Level

ORDER: list["Level"] = ["unknown", "low", "medium", "high"]
_BY_VERIFICATION: dict[str, "Level"] = {
    "text_layer": "high",
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


def overall(used: dict[str, "Fact"], warnings: int, caps: list[Cap] | None = None) -> Confidence:
    if not used:
        return Confidence("low", "no policy facts supported this result")
    name, weakest = min(used.items(), key=lambda kv: (ORDER.index(fact_level(kv[1])), kv[0]))
    level = fact_level(weakest)
    where = f", page {weakest.page}" if weakest.page else ""
    reason = f"weakest link: {name} ({weakest.verification.replace('_', ' ')}{where})"
    if level == "unknown":
        level = "low"

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
