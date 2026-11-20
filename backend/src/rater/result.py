"""The run result (spec SR21): the challenge example's keys, only ever extended, serialised
deterministically."""

import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from rater.facts import Facts

Status = Literal["resolved", "unsupported", "ambiguous"]


class _Model(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    def dump(self) -> dict[str, Any]:
        return self.model_dump(by_alias=True, mode="json")


class RateOut(_Model):
    applicable: bool | None = None
    rate_percent: float | None = None
    reason: str = ""
    raw_cell_value: str | None = None
    grid_citation: str | None = None
    citations: list[dict[str, Any]] = Field(default_factory=list)

    @classmethod
    def not_applicable(cls, reason: str) -> "RateOut":
        return cls(applicable=False, rate_percent=None, reason=reason)


class TraceStep(_Model):
    step: int
    kind: str
    decision: str
    policy_citation: str | None = None
    grid_citation: str | None = None
    citations: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ConfidenceOut(_Model):
    level: str
    reason: str
    capped_by: list[str] = Field(default_factory=list)


class NotApplied(_Model):
    rule: str
    why: str
    grid_citation: str | None = None


class Result(_Model):
    status: Status
    facts: Facts
    rates: dict[str, RateOut]
    trace: list[TraceStep]
    confidence: ConfidenceOut
    not_applied: list[NotApplied] = Field(default_factory=list)
    clarification: dict[str, list[str]] | None = None
    meta: dict[str, Any] = Field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps(self.dump(), sort_keys=True, ensure_ascii=False)
