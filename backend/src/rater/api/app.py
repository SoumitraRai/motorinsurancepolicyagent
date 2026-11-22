"""FastAPI application factory. `create_app_from_env` is the uvicorn entry point (`--factory`)."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from rater.api.auth import JwtVerifier
from rater.api.routes import RateLimiter, router

MAX_BYTES = 25 * 1024 * 1024
MAX_PAGES = 200  # only the first READ_PAGES (default 20) are OCR'd, so a long PDF stays cheap


@dataclass
class Deps:
    store: Any
    queue: Any
    objects: Any
    verifier: JwtVerifier
    static_dir: Path | None
    max_bytes: int = MAX_BYTES
    max_pages: int = MAX_PAGES
    limiter: RateLimiter = field(default_factory=lambda: RateLimiter(per_minute=10))


def create_app(deps: Deps) -> FastAPI:
    app = FastAPI(title="Brokerage Rate Agent", docs_url=None, redoc_url=None, openapi_url=None)
    app.state.deps = deps
    app.include_router(router)
    if deps.static_dir is not None and deps.static_dir.is_dir():
        # The SPA uses hash routes, so serving index.html at "/" is enough; no catch-all route.
        app.mount("/", StaticFiles(directory=deps.static_dir, html=True), name="spa")
    return app


def create_app_from_env() -> FastAPI:
    from rater.config import Settings, build_objects
    from rater.storage.postgres import PostgresStore

    settings = Settings.from_env()
    store = PostgresStore(settings.database_url)
    return create_app(
        Deps(
            store=store,
            queue=store,
            objects=build_objects(settings),
            verifier=settings.verifier(),
            static_dir=settings.static_dir,
        )
    )
