import hashlib
import uuid

import psycopg

from rater.storage.postgres import PostgresStore

USER_A = uuid.UUID("00000000-0000-0000-0000-00000000000a")
USER_B = uuid.UUID("00000000-0000-0000-0000-00000000000b")
PDF = b"%PDF-1.7 test bytes"
SHA = hashlib.sha256(PDF).hexdigest()


def _create(store: PostgresStore, user: uuid.UUID = USER_A, name: str = "policy.pdf"):
    return store.create_run(user, name, SHA, f"runs/{name}", page_count=3)


def test_run_roundtrip_after_reconnect(clean_db: str) -> None:
    first = PostgresStore(clean_db)
    run = _create(first)
    first.set_result(
        run.id,
        "resolved",
        '{"status": "resolved"}',
        versions={"ocr": "x"},
        switches={"GRID_DATE_POLICY": "warn"},
    )
    first.close()

    second = PostgresStore(clean_db)  # new process/connection, as after a restart or redeploy
    again = second.get_run(USER_A, run.id)
    assert again is not None
    assert again.status == "resolved"
    assert again.result_json == '{"status": "resolved"}'
    assert again.pdf_sha256 == SHA
    assert again.page_count == 3
    assert again.switches == {"GRID_DATE_POLICY": "warn"}


def test_other_user_cannot_read_run(clean_db: str) -> None:
    store = PostgresStore(clean_db)
    run = _create(store, USER_A)
    assert store.get_run(USER_B, run.id) is None
    assert store.list_runs(USER_B).items == []


def test_duplicate_upload_creates_two_runs(clean_db: str) -> None:
    store = PostgresStore(clean_db)
    one = _create(store)
    two = _create(store)
    assert one.id != two.id
    listed = store.list_runs(USER_A).items
    assert [r.id for r in listed] == [two.id, one.id]  # newest first


def test_list_runs_paginates(clean_db: str) -> None:
    store = PostgresStore(clean_db)
    ids = [_create(store, name=f"p{i}.pdf").id for i in range(5)]
    page1 = store.list_runs(USER_A, limit=2)
    page2 = store.list_runs(USER_A, cursor=page1.next_cursor, limit=2)
    page3 = store.list_runs(USER_A, cursor=page2.next_cursor, limit=2)
    got = [r.id for r in page1.items + page2.items + page3.items]
    assert got == list(reversed(ids))
    assert page3.next_cursor is None


def test_claim_marks_run_processing_and_complete(clean_db: str) -> None:
    store = PostgresStore(clean_db)
    run = _create(store)
    store.enqueue(run.id)
    job = store.claim()
    assert job is not None and job.run_id == run.id
    assert store.get_run(USER_A, run.id).status == "processing"  # type: ignore[union-attr]
    assert store.claim() is None  # nothing else queued
    store.complete(job.id)
    assert store.claim() is None


def test_stale_job_lock_is_reclaimed(clean_db: str) -> None:
    store = PostgresStore(clean_db)
    run = _create(store)
    store.enqueue(run.id)
    job = store.claim(lock_timeout_s=600)
    assert job is not None
    # Simulate a worker that died mid-run 20 minutes ago.
    with psycopg.connect(clean_db, autocommit=True) as conn:
        conn.execute("update jobs set locked_at = now() - interval '20 minutes' where id = %s", (job.id,))
    again = store.claim(lock_timeout_s=600)
    assert again is not None and again.id == job.id
    assert again.attempts == 2


def test_failed_job_sets_run_failed(clean_db: str) -> None:
    store = PostgresStore(clean_db)
    run = _create(store)
    store.enqueue(run.id)
    job = store.claim()
    assert job is not None
    store.fail(job.id, "boom")
    store.set_failed(run.id, "Analysis failed. Retry this run.")
    got = store.get_run(USER_A, run.id)
    assert got is not None and got.status == "failed" and got.error == "Analysis failed. Retry this run."


def test_audit_event_recorded(clean_db: str) -> None:
    store = PostgresStore(clean_db)
    run = _create(store)
    store.audit(str(USER_A), "run.created", f"run:{run.id}")
    with psycopg.connect(clean_db) as conn:
        rows = conn.execute("select actor, action, entity from audit_events").fetchall()
    assert rows == [(str(USER_A), "run.created", f"run:{run.id}")]
