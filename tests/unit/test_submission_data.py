"""The portable viewer must reject altered or inconsistent saved summaries."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pytest

from dashboard.submission_data import load_submission_evidence


@pytest.fixture
def evidence_root(tmp_path: Path) -> Path:
    for directory in ("docs/results/final", "docs/results/submission"):
        shutil.copytree(directory, tmp_path / directory)
    target = tmp_path / "docs/results/source-audit-2026-10-27.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile("docs/results/source-audit-2026-10-27.md", target)
    return tmp_path


def test_published_results_are_portable_without_runtime() -> None:
    evidence = load_submission_evidence(Path.cwd())
    assert len(evidence["results"]["runs"]) == 15
    assert evidence["source_counts"]["Missing numeric cells"]["clean"] == 19035190
    assert evidence["source_counts"]["Finite numeric readings"]["clean"] == 44238638
    assert evidence["runtime_reverified"] is False


def test_changed_summary_is_rejected(evidence_root: Path) -> None:
    path = evidence_root / "docs/results/final/final-results.json"
    path.write_bytes(path.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="binding"):
        load_submission_evidence(evidence_root)


def test_missing_evidence_is_rejected(evidence_root: Path) -> None:
    (evidence_root / "docs/results/final/final-coursework-scope.json").unlink()
    with pytest.raises(ValueError, match="missing"):
        load_submission_evidence(evidence_root)


def test_rebound_but_inconsistent_layer_counts_are_rejected(
    evidence_root: Path,
) -> None:
    path = evidence_root / "docs/results/final/final-results.json"
    data = json.loads(path.read_bytes())
    data["runs"][0]["layer_counts"]["bronze_deliveries"] += 1
    path.write_text(json.dumps(data), encoding="utf-8")
    index_path = evidence_root / "docs/results/submission/evidence-index.json"
    index = json.loads(index_path.read_bytes())
    entry = index["inputs"]["results"]
    entry["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    entry["byte_size"] = path.stat().st_size
    index_path.write_text(json.dumps(index), encoding="utf-8")
    with pytest.raises(ValueError, match="conservation"):
        load_submission_evidence(evidence_root)


def test_unknown_exposure_remains_unknown() -> None:
    evidence = load_submission_evidence(Path.cwd())
    restrictive = next(
        r
        for r in evidence["results"]["runs"]
        if r["run_id"] == "watermark-restrictive-r01"
    )
    assert restrictive["decision"]["incomparable_meter_period_count"] == 2
    assert all(
        row["residual_exposure_after_verification"] is None
        for row in restrictive["decision"]["tariff_scenarios"]
    )
