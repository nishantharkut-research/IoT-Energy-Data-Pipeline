"""Export exact validated summaries without inventing runtime files."""

import hashlib
import json
import shutil
from pathlib import Path

import pytest

from dashboard.submission_data import INPUTS
from scripts.export_dashboard_evidence import export_evidence


def test_export_preserves_all_input_bytes(tmp_path: Path) -> None:
    root = Path.cwd()
    export_evidence(root, tmp_path / "bundle")
    manifest = json.loads((tmp_path / "bundle/manifest.json").read_bytes())
    for name, entry in manifest["inputs"].items():
        payload = (tmp_path / "bundle" / entry["file"]).read_bytes()
        assert payload == (root / INPUTS[name]).read_bytes()
        assert hashlib.sha256(payload).hexdigest() == entry["sha256"]
    assert manifest["runtime_reverified"] is False
    assert not (tmp_path / "bundle/run-manifest.json").exists()


def test_export_rejects_changed_source_before_writing_bundle(tmp_path: Path) -> None:
    root = tmp_path / "source"
    for rel in [*INPUTS.values(), "docs/results/submission/evidence-index.json"]:
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(rel, target)
    source = root / INPUTS["results"]
    source.write_bytes(source.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="binding"):
        export_evidence(root, tmp_path / "bundle")
    assert not (tmp_path / "bundle/manifest.json").exists()
