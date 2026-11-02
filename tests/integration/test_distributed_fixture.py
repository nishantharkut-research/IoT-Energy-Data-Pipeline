from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from iot_energy_pipeline.distributed_fixture import prepare_distributed_fixture
from iot_energy_pipeline.replay import load_replay_manifest
from iot_energy_pipeline.schedule import load_schedule


def test_distributed_fixture_preparation_seals_cross_bound_artifacts(
    tmp_path: Path,
) -> None:
    run_dir = tmp_path / "distributed"

    plan = prepare_distributed_fixture(
        run_dir,
        run_id="docker-combined",
        fault="combined",
        watermark="1 minute",
        max_offsets_per_trigger=60,
    )

    saved = json.loads((run_dir / "distributed-plan.json").read_text("utf-8"))
    assert saved == plan
    assert plan["status"] == "prepared"
    assert plan["topic"] == "iot-energy-docker-combined"
    assert plan["max_offsets_per_trigger"] == 60
    schedule = load_schedule(run_dir / plan["schedule_path"])
    manifest = load_replay_manifest(run_dir / plan["replay_manifest_path"])
    canonical = run_dir / plan["canonical_ndjson_path"]
    assert schedule.schedule_hash == manifest.schedule_hash
    assert manifest.sha256() == plan["replay_manifest_hash"]
    assert hashlib.sha256(canonical.read_bytes()).hexdigest() == manifest.snapshot_hash
    assert plan["canonical_ndjson_sha256"] == manifest.snapshot_hash
    assert manifest.expected_delivery_count == len(schedule.deliveries)


def test_distributed_fixture_preparation_is_immutable(tmp_path: Path) -> None:
    run_dir = tmp_path / "distributed"
    prepare_distributed_fixture(run_dir, run_id="docker-clean", fault="clean")

    with pytest.raises(FileExistsError, match="already exists"):
        prepare_distributed_fixture(run_dir, run_id="docker-clean", fault="clean")


def test_distributed_fixture_exercises_exact_values_beyond_int64(
    tmp_path: Path,
) -> None:
    run_dir = tmp_path / "wide-fixture"
    prepare_distributed_fixture(run_dir, run_id="wide-fixture", fault="clean")
    events = [
        json.loads(line)
        for line in (run_dir / "snapshot/canonical.ndjson").read_text().splitlines()
    ]
    assert any(event["scaled_value"] > 2**63 - 1 for event in events)
    assert any(
        event["original_numeric_text"] == "26724.7"
        and event["decimal_scale"] == 15
        and event["scaled_value"] == 26724700000000000000
        for event in events
    )
