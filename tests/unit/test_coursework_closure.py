from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from scripts.close_coursework import PUBLISHED_FILES, verify_published_run


def saved_run(root: Path) -> str:
    artifacts = {}
    for relative in PUBLISHED_FILES:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"saved evidence\n")
        artifacts[relative] = {
            "relative_path": relative,
            "byte_size": path.stat().st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
    manifest = {
        "schema_version": "finalized-run-v1",
        "status": "finalized",
        "reconciled": True,
        "immutable": True,
        "artifacts": artifacts,
    }
    payload = json.dumps(manifest).encode()
    (root / "run-manifest.json").write_bytes(payload)
    digest = hashlib.sha256(payload).hexdigest()
    (root / "run-manifest.sha256").write_text(digest)
    return digest


def test_published_check_records_its_exact_coverage(tmp_path: Path) -> None:
    digest = saved_run(tmp_path)
    _, checked = verify_published_run(tmp_path, digest)
    assert set(checked) == PUBLISHED_FILES


def test_resealed_manifest_must_still_match_final_scope(tmp_path: Path) -> None:
    saved_run(tmp_path)
    with pytest.raises(ValueError, match="scope"):
        verify_published_run(tmp_path, "0" * 64)


def test_changed_published_output_is_rejected(tmp_path: Path) -> None:
    digest = saved_run(tmp_path)
    (tmp_path / "gold/gold-source-events.ndjson").write_bytes(b"altered\n")
    with pytest.raises(ValueError, match="artifact"):
        verify_published_run(tmp_path, digest)
