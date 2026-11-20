"""Request and response bodies. Requests reject unknown fields (secure-api-review rule 2)."""

import json
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from rater.storage.base import RunRow


class _Out(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class ClarifyBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    facts: dict[str, str] = Field(max_length=20)


class Created(_Out):
    id: UUID


class RunSummary(_Out):
    id: UUID
    file_name: str
    created_at: datetime
    status: str
    insurer: str | None = None
    od: dict[str, Any] | None = None
    tp: dict[str, Any] | None = None

    @classmethod
    def of(cls, run: RunRow) -> "RunSummary":
        result = json.loads(run.result_json) if run.result_json else {}
        insurer = (result.get("facts") or {}).get("insurer") or {}
        rates = result.get("rates") or {}
        return cls(
            id=run.id,
            file_name=run.file_name,
            created_at=run.created_at,
            status=run.status,
            insurer=insurer.get("value") if isinstance(insurer, dict) else None,
            od=rates.get("od"),
            tp=rates.get("tp"),
        )


class RunList(_Out):
    items: list[RunSummary]
    next_cursor: str | None


class RunDetail(_Out):
    id: UUID
    file_name: str
    created_at: datetime
    status: str
    page_count: int
    error: str | None
    parent_run_id: UUID | None
    overrides: dict[str, str] | None
    result: dict[str, Any] | None

    @classmethod
    def of(cls, run: RunRow) -> "RunDetail":
        return cls(
            id=run.id,
            file_name=run.file_name,
            created_at=run.created_at,
            status=run.status,
            page_count=run.page_count,
            error=run.error,
            parent_run_id=run.parent_run_id,
            overrides=run.overrides,
            result=json.loads(run.result_json) if run.result_json else None,
        )


class SignedUrl(_Out):
    url: str
