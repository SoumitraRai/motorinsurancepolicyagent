"""Postgres implementation of RunStore and JobQueue (Supabase Postgres in deployment)."""

import base64
import json
from datetime import datetime
from typing import Any
from uuid import UUID

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from rater.storage.base import Job, Page, RunRow

_COLUMNS = (
    "id, user_id, created_at, file_name, pdf_sha256, storage_key, page_count, status, "
    "result::text as result_json, error, parent_run_id, switches, versions, overrides"
)


def _row(r: dict[str, Any]) -> RunRow:
    return RunRow(**r)


def _encode_cursor(created_at: datetime, run_id: UUID) -> str:
    return base64.urlsafe_b64encode(json.dumps([created_at.isoformat(), str(run_id)]).encode()).decode()


def _decode_cursor(cursor: str) -> tuple[str, str]:
    created, run_id = json.loads(base64.urlsafe_b64decode(cursor.encode()))
    return created, run_id


class PostgresStore:
    def __init__(self, dsn: str) -> None:
        self._conn = psycopg.connect(dsn, autocommit=True, row_factory=dict_row)

    def close(self) -> None:
        self._conn.close()

    # RunStore
    def create_run(
        self,
        user_id: UUID,
        file_name: str,
        pdf_sha256: str,
        storage_key: str,
        page_count: int,
        parent_run_id: UUID | None = None,
        overrides: dict[str, str] | None = None,
    ) -> RunRow:
        row = self._conn.execute(
            f"insert into runs (user_id, file_name, pdf_sha256, storage_key, page_count, parent_run_id, "
            f"overrides) values (%s, %s, %s, %s, %s, %s, %s) returning {_COLUMNS}",
            (
                user_id,
                file_name,
                pdf_sha256,
                storage_key,
                page_count,
                parent_run_id,
                Jsonb(overrides) if overrides is not None else None,
            ),
        ).fetchone()
        assert row is not None
        return _row(row)

    def get_run(self, user_id: UUID, run_id: UUID) -> RunRow | None:
        row = self._conn.execute(
            f"select {_COLUMNS} from runs where id = %s and user_id = %s", (run_id, user_id)
        ).fetchone()
        return _row(row) if row else None

    def get_run_any_user(self, run_id: UUID) -> RunRow | None:
        row = self._conn.execute(f"select {_COLUMNS} from runs where id = %s", (run_id,)).fetchone()
        return _row(row) if row else None

    def list_runs(self, user_id: UUID, cursor: str | None = None, limit: int = 50) -> Page:
        params: list[Any] = [user_id]
        where = "user_id = %s"
        if cursor:
            created, run_id = _decode_cursor(cursor)
            where += " and (created_at, id) < (%s::timestamptz, %s::uuid)"
            params += [created, run_id]
        rows = self._conn.execute(
            f"select {_COLUMNS} from runs where {where} order by created_at desc, id desc limit %s",
            (*params, limit + 1),
        ).fetchall()
        items = [_row(r) for r in rows[:limit]]
        next_cursor = _encode_cursor(items[-1].created_at, items[-1].id) if len(rows) > limit else None
        return Page(items=items, next_cursor=next_cursor)

    def set_result(
        self, run_id: UUID, status: str, result_json: str, versions: dict[str, Any], switches: dict[str, Any]
    ) -> None:
        self._conn.execute(
            "update runs set status = %s, result = %s::jsonb, versions = %s, switches = %s, error = null, "
            "updated_at = clock_timestamp() where id = %s",
            (status, result_json, Jsonb(versions), Jsonb(switches), run_id),
        )

    def set_failed(self, run_id: UUID, error: str) -> None:
        self._conn.execute(
            "update runs set status = 'failed', error = %s, updated_at = clock_timestamp() where id = %s",
            (error, run_id),
        )

    def set_queued(self, run_id: UUID) -> None:
        self._conn.execute(
            "update runs set status = 'queued', error = null, updated_at = clock_timestamp() where id = %s",
            (run_id,),
        )

    def audit(self, actor: str, action: str, entity: str) -> None:
        self._conn.execute(
            "insert into audit_events (actor, action, entity) values (%s, %s, %s)", (actor, action, entity)
        )

    # JobQueue
    def enqueue(self, run_id: UUID) -> None:
        self._conn.execute("insert into jobs (run_id) values (%s)", (run_id,))

    def claim(self, lock_timeout_s: int = 600) -> Job | None:
        with self._conn.transaction():
            row = self._conn.execute(
                """
                update jobs set state = 'running', attempts = attempts + 1, locked_at = clock_timestamp()
                where id = (
                  select id from jobs
                  where state = 'queued'
                     or (state = 'running' and locked_at < clock_timestamp() - make_interval(secs => %s))
                  order by id
                  for update skip locked
                  limit 1
                )
                returning id, run_id, attempts
                """,
                (lock_timeout_s,),
            ).fetchone()
            if row is None:
                return None
            self._conn.execute(
                "update runs set status = 'processing', updated_at = clock_timestamp() where id = %s",
                (row["run_id"],),
            )
        return Job(id=row["id"], run_id=row["run_id"], attempts=row["attempts"])

    def complete(self, job_id: int) -> None:
        self._conn.execute("update jobs set state = 'done', locked_at = null where id = %s", (job_id,))

    def fail(self, job_id: int, error: str) -> None:
        self._conn.execute(
            "update jobs set state = 'failed', last_error = %s, locked_at = null where id = %s",
            (error, job_id),
        )
