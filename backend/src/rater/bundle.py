"""SHA-256 verification of the read-only starter bundle against its MANIFEST.json (spec SR11).

Grids are only ever loaded after `verify_bundle` succeeds; a mismatch stops the worker.
"""

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path

BUNDLE_ROOT = Path(
    os.environ.get("BUNDLE_ROOT", Path(__file__).resolve().parents[3] / "insurance-rater-agent-challenge")
)
# Operating-system metadata that is never part of the bundle.
_IGNORED_NAMES = {".DS_Store", "Thumbs.db"}


class BundleIntegrityError(Exception):
    def __init__(self, path: str, expected: str, actual: str) -> None:
        super().__init__(f"{path}: expected {expected}, found {actual}")
        self.path = path
        self.expected = expected
        self.actual = actual


@dataclass(frozen=True)
class BundleInfo:
    root: Path
    files: dict[str, str]  # bundle-relative path -> sha256
    manifest_sha256: str


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_bundle(root: Path = BUNDLE_ROOT) -> BundleInfo:
    manifest_path = root / "MANIFEST.json"
    manifest_bytes = manifest_path.read_bytes()
    listed = {f["path"]: f for f in json.loads(manifest_bytes)["files"]}

    for rel, entry in listed.items():
        path = root / rel
        if not path.is_file():
            raise BundleIntegrityError(rel, entry["sha256"], "missing")
        actual = _sha256(path)
        if actual != entry["sha256"] or path.stat().st_size != entry["bytes"]:
            raise BundleIntegrityError(rel, entry["sha256"], actual)

    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.name in _IGNORED_NAMES or path == manifest_path:
            continue
        rel = path.relative_to(root).as_posix()
        if rel not in listed:
            raise BundleIntegrityError(rel, "unlisted", _sha256(path))

    return BundleInfo(
        root=root,
        files={rel: entry["sha256"] for rel, entry in listed.items()},
        manifest_sha256=hashlib.sha256(manifest_bytes).hexdigest(),
    )
