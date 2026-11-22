"""Settings from the environment. Secrets come only from the host environment, never from files."""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from rater.api.auth import JwtVerifier, jwks_fetcher
from rater.storage.objects import LocalObjectStore, ObjectStore, SupabaseObjectStore
from rater.worker import Pipeline

if TYPE_CHECKING:
    from rater.pipeline import Deps

REPO_ROOT = Path(__file__).resolve().parents[3]


def _require(name: str) -> str:
    value = os.environ.get(name, "")
    if not value:
        raise RuntimeError(f"Set the {name} environment variable.")
    return value


@dataclass(frozen=True)
class Settings:
    database_url: str
    supabase_url: str | None
    supabase_service_key: str | None
    storage_bucket: str
    local_storage_dir: Path | None
    file_signing_secret: str | None
    static_dir: Path | None

    @classmethod
    def from_env(cls) -> "Settings":
        local = os.environ.get("LOCAL_STORAGE_DIR")
        static = os.environ.get("STATIC_DIR", str(REPO_ROOT / "frontend" / "dist"))
        return cls(
            database_url=_require("DATABASE_URL"),
            supabase_url=os.environ.get("SUPABASE_URL") or None,
            supabase_service_key=os.environ.get("SUPABASE_SERVICE_KEY") or None,
            storage_bucket=os.environ.get("STORAGE_BUCKET", "policies"),
            local_storage_dir=Path(local) if local else None,
            file_signing_secret=os.environ.get("FILE_SIGNING_SECRET") or None,
            static_dir=Path(static) if static else None,
        )

    def verifier(self) -> JwtVerifier:
        url = _require("SUPABASE_URL").rstrip("/")
        return JwtVerifier(keys=jwks_fetcher(f"{url}/auth/v1/.well-known/jwks.json"), issuer=f"{url}/auth/v1")


def build_objects(settings: Settings) -> ObjectStore:
    if settings.local_storage_dir is not None:
        return LocalObjectStore(settings.local_storage_dir, secret=_require("FILE_SIGNING_SECRET"))
    return SupabaseObjectStore(
        _require("SUPABASE_URL"), _require("SUPABASE_SERVICE_KEY"), bucket=settings.storage_bucket
    )


def build_deps() -> "Deps":
    from rater.bundle import BUNDLE_ROOT, verify_bundle
    from rater.extraction.ocr import RapidOcrEngine, TesseractEngine
    from rater.extraction.providers.base import choose_extractor
    from rater.extraction.providers.rules import RulesExtractor
    from rater.grids.registry import load_all
    from rater.pipeline import Deps
    from rater.switches import Switches

    info = verify_bundle(BUNDLE_ROOT)  # a mismatch raises and stops the worker (SR11)
    return Deps(
        gridset=load_all(BUNDLE_ROOT),
        engines=(RapidOcrEngine(), TesseractEngine()),
        primary=choose_extractor(),
        fallback=RulesExtractor(),
        switches=Switches.from_env(),
        grid_manifest=info.manifest_sha256,
        read_pages=int(os.environ.get("READ_PAGES", "20")) or None,  # 0 = read every page
    )


def build_pipeline(settings: Settings) -> Pipeline:
    from rater.pipeline import AnalysisPipeline

    return AnalysisPipeline(build_deps())
