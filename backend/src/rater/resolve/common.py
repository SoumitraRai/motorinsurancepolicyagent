"""Shared resolver types: a refusal carries its status, reason, evidence and the facts that would
settle it."""

from dataclasses import dataclass, field
from typing import Literal

from rater.citations import GridCite


@dataclass(frozen=True)
class Refusal:
    status: Literal["unsupported", "ambiguous"]
    reason: str
    cites: tuple[GridCite, ...] = ()
    missing: tuple[str, ...] = ()  # fact names that would settle an ambiguous result


@dataclass
class Step:
    kind: str
    decision: str
    facts: tuple[str, ...] = ()  # facts the step relied on (their policy citations go in the trace)
    cites: tuple[GridCite, ...] = ()
    warnings: list[str] = field(default_factory=list)
