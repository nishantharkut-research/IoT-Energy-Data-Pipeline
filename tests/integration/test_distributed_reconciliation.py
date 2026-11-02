from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from iot_energy_pipeline.run_reconciliation import reconcile_distributed_run


def _json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )


def _ndjson(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(
            json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n"
            for row in records
        ),
        encoding="utf-8",
    )


def _descriptor(path: Path, count: int, name: str) -> dict:
    return {
        "file": name,
        "local_file": name,
        "record_count": count,
        "byte_size": path.stat().st_size,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def _replay_evidence(run: Path) -> str:
    from dataclasses import asdict

    from iot_energy_pipeline.replay import make_manifest
    from iot_energy_pipeline.schedule import build_schedule

    plan_path = run / "distributed-plan.json"
    plan = json.loads(plan_path.read_text("utf-8"))
    canonical = run / "snapshot/canonical.ndjson"
    events = [json.loads(line) for line in canonical.read_text("utf-8").splitlines()]
    schedule = build_schedule(
        events,
        plan["run_id"],
        partition_count=plan["expected_terminal_count"],
        fault="duplicate" if len(events) == 1 else "clean",
    )
    plan["expected_delivery_count"] = len(schedule.deliveries)
    manifest = make_manifest(
        schedule,
        hashlib.sha256(canonical.read_bytes()).hexdigest(),
        requested_event_count=len(events),
    )
    replay = run / "replay"
    replay.mkdir()
    (replay / "replay-schedule.json").write_text(
        json.dumps(schedule.to_dict()), "utf-8"
    )
    (replay / "replay-manifest.json").write_text(json.dumps(asdict(manifest)), "utf-8")
    receipt = {
        "schema_version": "replay-receipt-v1",
        "status": "complete",
        "replay_run_id": plan["run_id"],
        "replay_manifest_hash": manifest.sha256(),
        "schedule_hash": schedule.schedule_hash,
        "expected_delivery_count": len(schedule.deliveries),
        "acknowledged_delivery_count": len(schedule.deliveries),
        "acknowledged_delivery_ids": [d.delivery_id for d in schedule.deliveries],
        "acknowledgements": [
            {
                "delivery_id": d.delivery_id,
                "partition": d.partition,
                "offset": d.position,
            }
            for d in schedule.deliveries
        ],
        "terminal_offsets": {str(p): 100 for p in range(schedule.partition_count)},
    }
    (replay / "replay-receipt.json").write_text(json.dumps(receipt), "utf-8")
    plan.update(
        canonical_ndjson_sha256=manifest.snapshot_hash,
        replay_manifest_path="replay/replay-manifest.json",
        replay_manifest_hash=manifest.sha256(),
        schedule_path="replay/replay-schedule.json",
        schedule_hash=schedule.schedule_hash,
    )
    plan_path.write_text(json.dumps(plan), "utf-8")
    return manifest.sha256()


def _prepared(tmp_path: Path) -> tuple[Path, Path, Path, str]:
    run = tmp_path / "run"
    oracle = tmp_path / "oracle"
    audit = tmp_path / "audit"
    replay_hash = "a" * 64
    source = {
        "source_event_id": "1" * 64,
        "meter_id": "meter-a",
        "value": 10,
        "event_time_utc": "2024-01-01T00:00:00Z",
    }
    aggregate = {"group_key": "meter-a|kWh|2", "count": 1, "sum_scaled": 10}
    canonical = run / "snapshot/canonical.ndjson"
    _ndjson(canonical, [source])
    _json(
        run / "distributed-plan.json",
        {
            "status": "prepared",
            "run_id": "fixture-run",
            "replay_manifest_hash": replay_hash,
            "canonical_ndjson_path": "snapshot/canonical.ndjson",
            "canonical_event_count": 1,
            "expected_delivery_count": 2,
            "expected_terminal_count": 1,
        },
    )
    gold_source = run / "gold/gold-source-events.ndjson"
    gold_aggregate = run / "gold/gold-aggregates.ndjson"
    _ndjson(gold_source, [source])
    _ndjson(gold_aggregate, [aggregate])
    _json(
        run / "gold/gold-manifest.json",
        {
            "schema_version": "distributed-gold-manifest-v1",
            "status": "gold_finalized",
            "replay_run_id": "fixture-run",
            "replay_manifest_hash": replay_hash,
            "bronze_delivery_count": 2,
            "terminal_record_count": 1,
            "source_coverage_count": 1,
            "aggregate_count": 1,
            "artifacts": {
                "gold_source_events_ndjson": _descriptor(
                    gold_source, 1, "gold-source-events.ndjson"
                ),
                "gold_aggregates_ndjson": _descriptor(
                    gold_aggregate, 1, "gold-aggregates.ndjson"
                ),
            },
        },
    )
    oracle_source = oracle / "hadoop-source-records.ndjson"
    oracle_aggregate = oracle / "hadoop-aggregates.ndjson"
    _ndjson(oracle_source, [source])
    _ndjson(oracle_aggregate, [aggregate])
    _json(
        oracle / "hadoop-oracle-manifest.json",
        {
            "schema_version": "hadoop-oracle-manifest-v2",
            "status": "complete",
            "run_id": "fixture-run",
            "input": {
                "local_sha256": hashlib.sha256(canonical.read_bytes()).hexdigest()
            },
            "outputs": {
                "aggregates": _descriptor(
                    oracle_aggregate, 1, "hadoop-aggregates.ndjson"
                ),
                "source_records": _descriptor(
                    oracle_source, 1, "hadoop-source-records.ndjson"
                ),
            },
        },
    )
    disposition = audit / "layer-dispositions.ndjson"
    _ndjson(disposition, [{"delivery_id": "one"}, {"delivery_id": "two"}])
    candidate = audit / "silver-candidate-events.ndjson"
    _ndjson(candidate, [source])
    _json(
        audit / "layer-audit-manifest.json",
        {
            "schema_version": "layer-audit-manifest-v1",
            "status": "complete",
            "replay_manifest_hash": replay_hash,
            "counts": {
                "bronze_deliveries": 2,
                "parsed_valid_deliveries": 2,
                "quarantine_deliveries": 0,
                "silver_deliveries": 1,
                "duplicate_valid_deliveries": 1,
                "late_valid_deliveries": 0,
                "terminal_records": 1,
            },
            "artifacts": {
                "layer_dispositions_ndjson": _descriptor(
                    disposition, 2, "layer-dispositions.ndjson"
                ),
                "silver_candidate_events_ndjson": _descriptor(
                    candidate, 1, "silver-candidate-events.ndjson"
                ),
            },
        },
    )
    import pyarrow as pa
    import pyarrow.parquet as pq

    from jobs.spark.finalize_distributed import _directory_manifest

    manifest_path = run / "gold/gold-manifest.json"
    manifest = json.loads(manifest_path.read_text("utf-8"))
    for name, directory in (
        ("source_events_parquet", "source-events.parquet"),
        ("aggregates_parquet", "aggregates.parquet"),
    ):
        tree = run / "gold" / directory
        tree.mkdir()
        pq.write_table(pa.table({"value": [10]}), tree / "part-000.parquet")
        manifest["artifacts"][name] = _directory_manifest(tree)
    _json(manifest_path, manifest)
    replay_hash = _replay_evidence(run)
    for path in (run / "gold/gold-manifest.json", audit / "layer-audit-manifest.json"):
        document = json.loads(path.read_text("utf-8"))
        document["replay_manifest_hash"] = replay_hash
        _json(path, document)
    return run, oracle, audit, replay_hash


def test_reconciliation_binds_layers_and_compares_both_oracle_outputs(
    tmp_path: Path,
) -> None:
    run, oracle, audit, replay_hash = _prepared(tmp_path)

    report = reconcile_distributed_run(
        run_dir=run,
        oracle_dir=oracle,
        layer_audit_dir=audit,
        output=run / "reports/reconciliation.json",
    )

    assert report["status"] == "passed"
    assert report["replay_manifest_hash"] == replay_hash
    assert report["aggregate_comparison"]["errors"] == []
    assert report["source_record_comparison"]["errors"] == []
    assert report["source_record_comparison"]["exact_fields"] == [
        "event_time_utc",
        "meter_id",
        "source_event_id",
        "value",
    ]
    assert report["bindings"]["silver_candidate_events_sha256"]


def test_field_difference_fails_reconciliation_without_finalizing(
    tmp_path: Path,
) -> None:
    run, oracle, audit, _ = _prepared(tmp_path)
    oracle_source = oracle / "hadoop-source-records.ndjson"
    changed = {
        "source_event_id": "1" * 64,
        "meter_id": "meter-a",
        "value": 11,
        "event_time_utc": "2024-01-01T00:00:00Z",
    }
    _ndjson(oracle_source, [changed])
    manifest_path = oracle / "hadoop-oracle-manifest.json"
    manifest = json.loads(manifest_path.read_text("utf-8"))
    manifest["outputs"]["source_records"] = _descriptor(
        oracle_source, 1, "hadoop-source-records.ndjson"
    )
    _json(manifest_path, manifest)

    report = reconcile_distributed_run(
        run_dir=run,
        oracle_dir=oracle,
        layer_audit_dir=audit,
        output=run / "reports/reconciliation.json",
    )

    assert report["status"] == "failed"
    assert "value" in report["source_record_comparison"]["errors"][0]


def test_accounting_or_artifact_tampering_is_rejected(tmp_path: Path) -> None:
    run, oracle, audit, _ = _prepared(tmp_path)
    (run / "gold/gold-aggregates.ndjson").write_text("tampered\n", encoding="utf-8")

    with pytest.raises(ValueError, match="artifact integrity"):
        reconcile_distributed_run(
            run_dir=run,
            oracle_dir=oracle,
            layer_audit_dir=audit,
            output=run / "reports/reconciliation.json",
        )


def test_reconciliation_output_is_immutable(tmp_path: Path) -> None:
    run, oracle, audit, _ = _prepared(tmp_path)
    output = run / "reports/reconciliation.json"
    output.parent.mkdir(parents=True)
    output.write_text("existing", encoding="utf-8")

    with pytest.raises(FileExistsError, match="immutable reconciliation"):
        reconcile_distributed_run(
            run_dir=run,
            oracle_dir=oracle,
            layer_audit_dir=audit,
            output=output,
        )


def test_reconciliation_rejects_non_integer_layer_counts(tmp_path: Path) -> None:
    run, oracle, audit, _ = _prepared(tmp_path)
    manifest_path = audit / "layer-audit-manifest.json"
    manifest = json.loads(manifest_path.read_text("utf-8"))
    manifest["counts"]["parsed_valid_deliveries"] = "2"
    _json(manifest_path, manifest)

    with pytest.raises(ValueError, match="layer count.*invalid"):
        reconcile_distributed_run(
            run_dir=run,
            oracle_dir=oracle,
            layer_audit_dir=audit,
            output=run / "reports/reconciliation.json",
        )


@pytest.mark.parametrize("directory", ["source-events.parquet", "aggregates.parquet"])
@pytest.mark.parametrize("mutation", ["bytes", "extra", "missing"])
def test_reconciliation_checks_gold_parquet_trees(
    tmp_path: Path,
    directory: str,
    mutation: str,
) -> None:
    run, oracle, audit, _ = _prepared(tmp_path)
    original = run / "reports/original-reconciliation.json"
    reconcile_distributed_run(
        run_dir=run, oracle_dir=oracle, layer_audit_dir=audit, output=original
    )
    report_bytes = original.read_bytes()
    tree = run / "gold" / directory
    part = tree / "part-000.parquet"
    if mutation == "bytes":
        payload = bytearray(part.read_bytes())
        payload[len(payload) // 2] ^= 1
        part.write_bytes(payload)
    elif mutation == "extra":
        (tree / "extra.parquet").write_bytes(part.read_bytes())
    else:
        part.unlink()
    output = run / "reports/reconciliation.json"
    with pytest.raises(ValueError, match="integrity"):
        reconcile_distributed_run(
            run_dir=run, oracle_dir=oracle, layer_audit_dir=audit, output=output
        )
    assert not output.exists()
    assert original.read_bytes() == report_bytes


@pytest.mark.parametrize(
    "relative",
    [
        "snapshot/canonical.ndjson",
        "replay/replay-schedule.json",
        "replay/replay-receipt.json",
    ],
)
def test_reconciliation_refuses_replay_bytes_changed_after_report(
    tmp_path: Path,
    relative: str,
) -> None:
    run, oracle, audit, _ = _prepared(tmp_path)
    original = run / "reports/original-reconciliation.json"
    reconcile_distributed_run(
        run_dir=run, oracle_dir=oracle, layer_audit_dir=audit, output=original
    )
    report_bytes = original.read_bytes()
    path = run / relative
    payload = bytearray(path.read_bytes())
    payload[len(payload) // 2] ^= 1
    path.write_bytes(payload)
    output = run / "reports/reconciliation.json"
    with pytest.raises(ValueError):
        reconcile_distributed_run(
            run_dir=run, oracle_dir=oracle, layer_audit_dir=audit, output=output
        )
    assert not output.exists()
    assert original.read_bytes() == report_bytes


def test_reconciliation_requires_query_parquet_descriptors(tmp_path: Path) -> None:
    run, oracle, audit, _ = _prepared(tmp_path)
    path = run / "gold/gold-manifest.json"
    manifest = json.loads(path.read_text("utf-8"))
    manifest["artifacts"].pop("source_events_parquet")
    _json(path, manifest)
    with pytest.raises(ValueError, match="integrity"):
        reconcile_distributed_run(
            run_dir=run,
            oracle_dir=oracle,
            layer_audit_dir=audit,
            output=run / "reports/reconciliation.json",
        )


@pytest.mark.parametrize(
    "name,directory",
    [
        ("source_events_parquet", "source-events.parquet"),
        ("aggregates_parquet", "aggregates.parquet"),
    ],
)
def test_reconciliation_rejects_descriptor_for_different_query_directory(
    tmp_path: Path,
    name: str,
    directory: str,
) -> None:
    run, oracle, audit, _ = _prepared(tmp_path)
    tree = run / "gold" / directory
    tree.rename(tree.with_name("other-" + directory))
    path = run / "gold/gold-manifest.json"
    manifest = json.loads(path.read_text("utf-8"))
    manifest["artifacts"][name]["directory"] = "other-" + directory
    _json(path, manifest)
    with pytest.raises(ValueError, match="integrity binding"):
        reconcile_distributed_run(
            run_dir=run,
            oracle_dir=oracle,
            layer_audit_dir=audit,
            output=run / "reports/reconciliation.json",
        )
