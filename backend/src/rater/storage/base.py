"""Storage boundary: runs, the job queue and audit events. Implementations live beside this module."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID


@dataclass(frozen=True)
class RunRow:
    id: UUID
    user_id: UUID
    created_at: datetime
    file_name: str
    pdf_sha256: str
    storage_key: str
    page_count: int
    status: str
    result_json: str | None = None
    error: str | None = None
    parent_run_id: UUID | None = None
    switches: dict[str, Any] | None = None
    versions: dict[str, Any] | None = None


@dataclass(frozen=True)
class Job:
    id: int
    run_id: UUID
    attempts: int


@dataclass(frozen=True)
class Page:
    items: list[RunRow] = field(default_factory=list)
    next_cursor: str | None = None


class RunStore(Protocol):
    def create_run(
        self,
        user_id: UUID,
        file_name: str,
        pdf_sha256: str,
        storage_key: str,
        page_count: int,
        parent_run_id: UUID | None = None,
    ) -> RunRow: ...

    def get_run(self, user_id: UUID, run_id: UUID) -> RunRow | None: ...

    def get_run_any_user(self, run_id: UUID) -> RunRow | None: ...

    def list_runs(self, user_id: UUID, cursor: str | None = None, limit: int = 50) -> Page: ...

    def set_result(
        self, run_id: UUID, status: str, result_json: str, versions: dict[str, Any], switches: dict[str, Any]
    ) -> None: ...

    def set_failed(self, run_id: UUID, error: str) -> None: ...

    def audit(self, actor: str, action: str, entity: str) -> None: ...


class JobQueue(Protocol):
    def enqueue(self, run_id: UUID) -> None: ...

    def claim(self, lock_timeout_s: int = 600) -> Job | None: ...

    def complete(self, job_id: int) -> None: ...

    def fail(self, job_id: int, error: str) -> None: ...
