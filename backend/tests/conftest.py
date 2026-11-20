"""Shared fixtures. Postgres runs in a throwaway Docker container for the whole session."""

import shutil
import socket
import subprocess
import time
import uuid
from collections.abc import Iterator
from pathlib import Path

import psycopg
import pytest

REPO = Path(__file__).resolve().parents[2]
MIGRATIONS = REPO / "migrations"


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


@pytest.fixture(scope="session")
def postgres_dsn() -> Iterator[str]:
    if shutil.which("docker") is None:
        pytest.fail("Docker is required for storage tests (plan T2).")
    port = _free_port()
    name = f"rater-test-pg-{uuid.uuid4().hex[:8]}"
    subprocess.run(
        [
            "docker",
            "run",
            "-d",
            "--rm",
            "--name",
            name,
            "-e",
            "POSTGRES_PASSWORD=test",
            "-p",
            f"127.0.0.1:{port}:5432",
            "postgres:16",
        ],
        check=True,
        capture_output=True,
    )
    dsn = f"postgresql://postgres:test@127.0.0.1:{port}/postgres"
    try:
        deadline = time.monotonic() + 60
        while True:
            try:
                with psycopg.connect(dsn, connect_timeout=2):
                    break
            except psycopg.OperationalError:
                if time.monotonic() > deadline:
                    raise
                time.sleep(0.5)
        with psycopg.connect(dsn, autocommit=True) as conn:
            for sql in sorted(MIGRATIONS.glob("*.sql")):
                conn.execute(sql.read_text())
        yield dsn
    finally:
        subprocess.run(["docker", "rm", "-f", name], check=False, capture_output=True)


@pytest.fixture
def clean_db(postgres_dsn: str) -> str:
    with psycopg.connect(postgres_dsn, autocommit=True) as conn:
        conn.execute("truncate audit_events, pages, jobs, runs restart identity cascade")
    return postgres_dsn
