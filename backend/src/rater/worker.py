"""Background worker: claims queued runs, runs the analysis pipeline, stores the result.

Logs carry only run ids, step names, durations and exception class names (spec C10 / AC20): never fact
values, quotes, file names or file contents.
"""

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Protocol

from rater.storage.base import JobQueue, RunStore
from rater.storage.objects import ObjectStore

log = logging.getLogger("rater.worker")

FAILED_MESSAGE = "Analysis failed. Retry this run."


@dataclass(frozen=True)
class PipelineOutput:
    status: str
    result_json: str
    versions: dict[str, Any] = field(default_factory=dict)
    switches: dict[str, Any] = field(default_factory=dict)


class Pipeline(Protocol):
    def __call__(
        self, pdf: bytes, file_name: str, overrides: dict[str, str] | None = None
    ) -> PipelineOutput: ...


class NotReadyPipeline:
    """Placeholder until the analysis engine lands (plan T13). It refuses honestly and never answers."""

    def __call__(self, pdf: bytes, file_name: str, overrides: dict[str, str] | None = None) -> PipelineOutput:
        result = {
            "status": "unsupported",
            "facts": {},
            "rates": {
                "od": {"applicable": None, "ratePercent": None, "reason": "analysis engine not deployed"},
                "tp": {"applicable": None, "ratePercent": None, "reason": "analysis engine not deployed"},
            },
            "trace": [],
            "confidence": {"level": "low", "reason": "analysis engine not deployed"},
        }
        return PipelineOutput("unsupported", json.dumps(result, sort_keys=True), versions={"engine": "none"})


def process_one(store: RunStore, queue: JobQueue, objects: ObjectStore, pipeline: Pipeline) -> bool:
    """Process at most one queued job. Returns False when there was nothing to do."""
    job = queue.claim()
    if job is None:
        return False
    started = time.monotonic()
    log.info("run %s: claimed (attempt %d)", job.run_id, job.attempts)
    run = store.get_run_any_user(job.run_id)
    if run is None:
        queue.fail(job.id, "run missing")
        log.warning("run %s: missing, job %d failed", job.run_id, job.id)
        return True
    try:
        pdf = objects.get(run.storage_key)
        out = pipeline(pdf, run.file_name, run.overrides)
        store.set_result(run.id, out.status, out.result_json, out.versions, out.switches)
        queue.complete(job.id)
        log.info("run %s: %s in %.1fs", run.id, out.status, time.monotonic() - started)
    except Exception as exc:  # the worker must survive any single bad run
        queue.fail(job.id, type(exc).__name__)
        store.set_failed(run.id, FAILED_MESSAGE)
        log.error(
            "run %s: failed with %s after %.1fs", run.id, type(exc).__name__, time.monotonic() - started
        )
    return True


def run_forever(
    store: RunStore, queue: JobQueue, objects: ObjectStore, pipeline: Pipeline, poll_s: float = 2.0
) -> None:
    while True:
        if not process_one(store, queue, objects, pipeline):
            time.sleep(poll_s)


def main() -> None:
    from rater.config import Settings, build_objects, build_pipeline
    from rater.storage.postgres import PostgresStore

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    settings = Settings.from_env()
    store = PostgresStore(settings.database_url)
    run_forever(store, store, build_objects(settings), build_pipeline(settings))


if __name__ == "__main__":
    main()
