import json
import shutil
from pathlib import Path

import pytest

from rater.bundle import BUNDLE_ROOT, BundleIntegrityError, verify_bundle


def test_manifest_all_files_ok() -> None:
    info = verify_bundle(BUNDLE_ROOT)
    manifest = json.loads((BUNDLE_ROOT / "MANIFEST.json").read_text())
    assert set(info.files) == {f["path"] for f in manifest["files"]}
    assert len(info.manifest_sha256) == 64


def _copy(tmp_path: Path) -> Path:
    dst = tmp_path / "bundle"
    shutil.copytree(BUNDLE_ROOT, dst)
    return dst


def test_tampered_copy_fails(tmp_path: Path) -> None:
    root = _copy(tmp_path)
    target = root / "raters" / "tata-aig"
    xlsx = next(target.rglob("*.xlsx"))
    data = bytearray(xlsx.read_bytes())
    data[len(data) // 2] ^= 0x01
    xlsx.write_bytes(bytes(data))
    with pytest.raises(BundleIntegrityError) as err:
        verify_bundle(root)
    assert err.value.path == str(xlsx.relative_to(root))
    assert err.value.expected != err.value.actual


def test_missing_file_fails(tmp_path: Path) -> None:
    root = _copy(tmp_path)
    next((root / "raters").rglob("*.pdf")).unlink()
    with pytest.raises(BundleIntegrityError) as err:
        verify_bundle(root)
    assert err.value.actual == "missing"


def test_unlisted_file_fails_but_finder_metadata_ignored(tmp_path: Path) -> None:
    root = _copy(tmp_path)
    (root / "raters" / ".DS_Store").write_bytes(b"finder")
    verify_bundle(root)  # macOS metadata is not part of the bundle
    (root / "raters" / "extra.xlsx").write_bytes(b"x")
    with pytest.raises(BundleIntegrityError) as err:
        verify_bundle(root)
    assert err.value.expected == "unlisted"
