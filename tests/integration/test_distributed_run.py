from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

from iot_energy_pipeline.distributed_run import main, prepare_distributed_run
from iot_energy_pipeline.replay import load_replay_manifest


def _write_ndjson(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )


def _snapshot(tmp_path: Path) -> Path:
    snapshot = tmp_path / "snapshot"
    canonical = snapshot / "canonical.ndjson"
    records = [
        {
            "schema_version": "canonical-event-v1",
            "source_event_id": f"{index:064x}",
            "meter_id": "meter-a",
            "event_time_utc": f"2024-01-01T0{index}:00:00Z",
            "scaled_value": index,
            "decimal_scale": 0,
            "unit": "kWh",
            "quality_flags": [],
        }
        for index in range(1, 4)
    ]
    _write_ndjson(canonical, records)
    (snapshot / "snapshot-manifest.json").write_text(
        json.dumps(
            {
                "schema_version": "snapshot-manifest-v1",
                "status": "complete",
                "artifacts": {
                    "canonical_ndjson": {
                        "file": "canonical.ndjson",
                        "record_count": 3,
                        "sha256": hashlib.sha256(canonical.read_bytes()).hexdigest(),
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    return snapshot


def test_distributed_run_preparation_selects_a_deterministic_prefix(
    tmp_path: Path,
) -> None:
    snapshot = _snapshot(tmp_path)
    output = tmp_path / "run"

    plan = prepare_distributed_run(
        snapshot_dir=snapshot,
        output_dir=output,
        run_id="scale-2-r01",
        fault="clean",
        event_count=2,
        seed=20260825,
        partition_count=3,
        watermark="24 hours",
        max_offsets_per_trigger=1000,
    )

    selected = (output / "snapshot/canonical.ndjson").read_text("utf-8").splitlines()
    assert len(selected) == 2
    assert plan["canonical_event_count"] == 2
    assert plan["full_snapshot_event_count"] == 3
    assert plan["selection"] == "source_event_id_sorted_prefix"
    assert plan["schema_version"] == "distributed-run-plan-v2"
    assert plan["schedule_format"] == "delivery-ndjson-v2"
    schedule_path = output / plan["schedule_path"]
    schedule = [
        json.loads(line) for line in schedule_path.read_text("utf-8").splitlines()
    ]
    assert [item["position"] for item in schedule] == [0, 1]
    assert (
        plan["schedule_hash"] == hashlib.sha256(schedule_path.read_bytes()).hexdigest()
    )
    metadata = json.loads(
        (output / plan["schedule_metadata_path"]).read_text(encoding="utf-8")
    )
    assert metadata["delivery_count"] == 2
    assert metadata["schedule_sha256"] == plan["schedule_hash"]
    assert (
        plan["source_snapshot_sha256"]
        == hashlib.sha256((snapshot / "canonical.ndjson").read_bytes()).hexdigest()
    )
    assert plan["expected_delivery_count"] == 2
    assert (
        json.loads((output / "replay/replay-manifest.json").read_text("utf-8"))[
            "repetition"
        ]
        == 1
    )
    assert json.loads((output / "distributed-plan.json").read_text("utf-8")) == plan


def test_distributed_run_preparation_rejects_snapshot_tampering(
    tmp_path: Path,
) -> None:
    snapshot = _snapshot(tmp_path)
    (snapshot / "canonical.ndjson").write_text("tampered\n", encoding="utf-8")

    with pytest.raises(ValueError, match="snapshot integrity"):
        prepare_distributed_run(
            snapshot_dir=snapshot,
            output_dir=tmp_path / "run",
            run_id="scale-2-r01",
            fault="clean",
            event_count=2,
        )


def test_distributed_run_preparation_is_immutable(tmp_path: Path) -> None:
    snapshot = _snapshot(tmp_path)
    output = tmp_path / "run"
    output.mkdir()

    with pytest.raises(FileExistsError, match="already exists"):
        prepare_distributed_run(
            snapshot_dir=snapshot,
            output_dir=output,
            run_id="scale-2-r01",
            fault="clean",
            event_count=2,
        )


@pytest.mark.parametrize("repetition", [1, 2, 3])
def test_distributed_run_binds_repetition(tmp_path: Path, repetition: int) -> None:
    output = tmp_path / "run"
    plan = prepare_distributed_run(
        snapshot_dir=_snapshot(tmp_path),
        output_dir=output,
        run_id=f"scale-2-r{repetition:02d}",
        fault="clean",
        event_count=2,
        repetition=repetition,
    )
    manifest = json.loads((output / "replay/replay-manifest.json").read_text("utf-8"))
    assert manifest["repetition"] == repetition
    assert (
        load_replay_manifest(output / "replay/replay-manifest.json").sha256()
        == (plan["replay_manifest_hash"])
    )


@pytest.mark.parametrize("repetition", [True, 0, -1, "2", 1.5, None])
def test_distributed_run_rejects_invalid_repetition(
    tmp_path: Path, repetition: object
) -> None:
    output = tmp_path / "run"
    with pytest.raises(ValueError, match="repetition"):
        prepare_distributed_run(
            snapshot_dir=_snapshot(tmp_path),
            output_dir=output,
            run_id="scale-2-r01",
            fault="clean",
            event_count=2,
            repetition=repetition,
        )
    assert not output.exists()


def test_prepare_cli_passes_repetition(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "run"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "distributed_run",
            "prepare",
            "--snapshot-dir",
            str(_snapshot(tmp_path)),
            "--output",
            str(output),
            "--run-id",
            "scale-2-r03",
            "--fault",
            "clean",
            "--event-count",
            "2",
            "--repetition",
            "3",
        ],
    )
    assert main() == 0
    manifest = json.loads((output / "replay/replay-manifest.json").read_text("utf-8"))
    assert manifest["repetition"] == 3
