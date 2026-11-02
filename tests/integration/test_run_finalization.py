from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from dashboard.data import REQUIRED_VIEWS, load_finalized_run
from iot_energy_pipeline.run_finalization import seal_distributed_run


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n", "utf-8")


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _replay_evidence(run: Path, streaming: bool = False) -> str:
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
    if streaming:
        from dataclasses import replace

        from iot_energy_pipeline.streaming_replay import write_streaming_schedule

        metadata = write_streaming_schedule(
            canonical,
            replay / "replay-schedule.ndjson",
            run_id=plan["run_id"],
            seed=0,
            partition_count=schedule.partition_count,
            fault="clean",
        )
        metadata_path = replay / "replay-schedule-metadata.json"
        _write_json(metadata_path, metadata.to_dict())
        manifest = replace(manifest, schedule_hash=metadata.schedule_sha256)
        _write_json(replay / "replay-manifest.json", asdict(manifest))
        acknowledgements = replay / "replay-acknowledgements.ndjson"
        acknowledgements.write_text(
            "".join(
                json.dumps(
                    {
                        "position": d.position,
                        "delivery_id": d.delivery_id,
                        "partition": d.partition,
                        "offset": d.position,
                    }
                )
                + "\n"
                for d in schedule.deliveries
            ),
            "utf-8",
        )
        receipt.pop("acknowledgements")
        receipt.pop("acknowledged_delivery_ids")
        receipt.update(
            schema_version="replay-receipt-v2",
            replay_manifest_hash=manifest.sha256(),
            schedule_hash=metadata.schedule_sha256,
            acknowledgement_ledger={
                "file": acknowledgements.name,
                "record_count": len(schedule.deliveries),
                "byte_size": acknowledgements.stat().st_size,
                "sha256": _hash(acknowledgements),
            },
        )
        _write_json(replay / "replay-receipt.json", receipt)
        plan.update(
            schedule_format="delivery-ndjson-v2",
            schedule_metadata_path="replay/replay-schedule-metadata.json",
            schedule_metadata_sha256=_hash(metadata_path),
        )
    plan.update(
        canonical_ndjson_sha256=manifest.snapshot_hash,
        replay_manifest_path="replay/replay-manifest.json",
        replay_manifest_hash=manifest.sha256(),
        schedule_path="replay/replay-schedule.json",
        schedule_hash=manifest.schedule_hash,
    )
    if streaming:
        plan["schedule_path"] = "replay/replay-schedule.ndjson"
    plan_path.write_text(json.dumps(plan), "utf-8")
    return manifest.sha256()


def _prepared(
    tmp_path: Path, streaming: bool = False
) -> tuple[Path, Path, Path, Path, Path]:
    run = tmp_path / "run"
    oracle = run / "oracle"
    audit = run / "layer-audit"
    reports = run / "reports"
    machine = run / "machine-metadata.json"
    replay_hash = "a" * 64
    _write_json(
        run / "distributed-plan.json",
        {
            "schema_version": "distributed-fixture-plan-v1",
            "status": "prepared",
            "run_id": "sealed-fixture",
            "fault": "combined",
            "seed": 20260825,
            "watermark": "1 minute",
            "canonical_event_count": 3,
            "expected_delivery_count": 5,
            "expected_terminal_count": 3,
            "replay_manifest_hash": replay_hash,
            "canonical_ndjson_sha256": "b" * 64,
        },
    )
    _write_json(
        run / "gold/gold-manifest.json",
        {
            "schema_version": "distributed-gold-manifest-v1",
            "status": "gold_finalized",
            "replay_run_id": "sealed-fixture",
            "replay_manifest_hash": replay_hash,
            "source_coverage_count": 3,
        },
    )
    _write_json(
        oracle / "hadoop-oracle-manifest.json",
        {
            "schema_version": "hadoop-oracle-manifest-v2",
            "status": "complete",
            "run_id": "sealed-fixture",
        },
    )
    _write_json(
        audit / "layer-audit-manifest.json",
        {
            "schema_version": "layer-audit-manifest-v1",
            "status": "complete",
            "replay_manifest_hash": replay_hash,
            "counts": {
                "bronze_deliveries": 5,
                "parsed_valid_deliveries": 4,
                "quarantine_deliveries": 1,
                "silver_deliveries": 3,
                "duplicate_valid_deliveries": 1,
                "late_valid_deliveries": 0,
                "terminal_records": 3,
            },
            "disposition_counts": {
                "silver": 3,
                "duplicate_valid": 1,
                "quarantine": 1,
            },
        },
    )
    reconciliation = reports / "reconciliation.json"
    _write_json(
        reconciliation,
        {
            "schema_version": "reconciliation-v2",
            "status": "passed",
            "run_id": "sealed-fixture",
            "replay_manifest_hash": replay_hash,
            "layer_counts": {
                "bronze_deliveries": 5,
                "silver_deliveries": 3,
                "quarantine_deliveries": 1,
            },
            "aggregate_comparison": {
                "spark_record_count": 1,
                "hadoop_record_count": 1,
                "errors": [],
            },
            "source_record_comparison": {
                "spark_record_count": 3,
                "hadoop_record_count": 3,
                "errors": [],
            },
            "bindings": {
                "gold_manifest_sha256": _hash(run / "gold/gold-manifest.json"),
                "hadoop_manifest_sha256": _hash(oracle / "hadoop-oracle-manifest.json"),
                "layer_audit_manifest_sha256": _hash(
                    audit / "layer-audit-manifest.json"
                ),
            },
        },
    )
    decision = reports / "decision-impact.json"
    _write_json(
        decision,
        {
            "schema_version": "decision-impact-v1",
            "status": "verified",
            "run_id": "sealed-fixture",
            "reconciliation_sha256": _hash(reconciliation),
            "candidate_interval_count": 1,
            "verified_interval_count": 2,
            "comparable_meter_period_count": 1,
            "incomparable_meter_period_count": 1,
            "numeric_discrepancy_meter_period_count": 1,
            "comparison_scope": "identical meter/start/end supports only",
            "coverage_limits": ["Unavailable consumption remains unknown"],
            "affected_meter_period_count": 1,
            "absolute_kwh_discrepancy": "2",
            "candidate_flagged_record_count": 1,
            "verified_flagged_record_count": 1,
            "verification_seconds": 7.5,
            "candidate_storage_bytes": 100,
            "verification_storage_bytes": 400,
            "storage_overhead_ratio": 4.0,
            "tariff_scenarios": [
                {
                    "normalized_rate": rate,
                    "gross_exposure": exposure,
                    "monetary_interpretation": (
                        "scenario only; not an HKUST financial result"
                    ),
                }
                for rate, exposure in (("0.5", "1"), ("1.0", "2"), ("2.0", "4"))
            ],
        },
    )
    _write_json(
        machine,
        {
            "schema_version": "machine-metadata-v1",
            "captured_at_utc": "2026-08-26T10:00:00Z",
            "execution_context": "fixture",
            "hostname": "coursework-host",
            "operating_system": "Windows",
            "processor": "fixture-cpu",
            "logical_cpu_count": 8,
            "memory_bytes": 17179869184,
            "software": {
                "python": "3.11.9",
                "docker": "deferred",
                "kafka": "apache/kafka:3.7.1",
                "spark": "3.5.1",
                "hadoop": "3.3.6",
            },
        },
    )
    from jobs.spark.finalize_distributed import _directory_manifest

    canonical = run / "snapshot/canonical.ndjson"
    canonical.parent.mkdir(parents=True)
    canonical.write_text(
        "".join(
            json.dumps(
                {
                    "source_event_id": f"{i:064x}",
                    "event_time_utc": f"2024-01-01T0{i}:00:00Z",
                }
            )
            + "\n"
            for i in range(3)
        ),
        "utf-8",
    )
    plan_path = run / "distributed-plan.json"
    plan = json.loads(plan_path.read_text("utf-8"))
    plan["canonical_ndjson_path"] = "snapshot/canonical.ndjson"
    plan["canonical_ndjson_sha256"] = _hash(canonical)
    _write_json(plan_path, plan)
    replay_hash = _replay_evidence(run, streaming)
    bindings = json.loads(reconciliation.read_text("utf-8"))["bindings"]
    bindings["canonical_ndjson_sha256"] = _hash(canonical)
    for root, manifest_name, registry_name, names, path_field, binding in (
        (
            run / "gold",
            "gold-manifest.json",
            "artifacts",
            ("gold_source_events_ndjson", "gold_aggregates_ndjson"),
            "file",
            "gold_manifest_sha256",
        ),
        (
            oracle,
            "hadoop-oracle-manifest.json",
            "outputs",
            ("source_records", "aggregates"),
            "local_file",
            "hadoop_manifest_sha256",
        ),
        (
            audit,
            "layer-audit-manifest.json",
            "artifacts",
            ("silver_candidate_events_ndjson", "layer_dispositions_ndjson"),
            "file",
            "layer_audit_manifest_sha256",
        ),
    ):
        manifest_path = root / manifest_name
        manifest = json.loads(manifest_path.read_text("utf-8"))
        manifest["replay_manifest_hash"] = replay_hash
        artifacts = {}
        for name in names:
            path = root / (name + ".ndjson")
            path.write_bytes(canonical.read_bytes())
            artifacts[name] = {
                path_field: path.name,
                "record_count": 1,
                "byte_size": path.stat().st_size,
                "sha256": _hash(path),
            }
            if name == "silver_candidate_events_ndjson":
                bindings["silver_candidate_events_sha256"] = _hash(path)
        if root == run / "gold":
            import pyarrow as pa
            import pyarrow.parquet as pq

            for name, directory in (
                ("source_events_parquet", "source-events.parquet"),
                ("aggregates_parquet", "aggregates.parquet"),
            ):
                tree = root / directory
                tree.mkdir()
                pq.write_table(pa.table({"value": [1]}), tree / "part-000.parquet")
                artifacts[name] = _directory_manifest(tree)
        if root == oracle:
            manifest["input"] = {"local_sha256": _hash(canonical)}
        manifest[registry_name] = artifacts
        _write_json(manifest_path, manifest)
        bindings[binding] = _hash(manifest_path)
    report = json.loads(reconciliation.read_text("utf-8"))
    plan = json.loads((run / "distributed-plan.json").read_text("utf-8"))
    bindings["replay_schedule_sha256"] = _hash(run / plan["schedule_path"])
    if streaming:
        bindings["replay_acknowledgements_sha256"] = _hash(
            run / "replay/replay-acknowledgements.ndjson"
        )
    bindings["replay_receipt_sha256"] = _hash(run / "replay/replay-receipt.json")
    report["replay_manifest_hash"] = replay_hash
    report["bindings"] = bindings
    _write_json(reconciliation, report)
    report = json.loads(decision.read_text("utf-8"))
    report["reconciliation_sha256"] = _hash(reconciliation)
    _write_json(decision, report)
    return run, oracle, audit, reconciliation, decision


def test_finalizer_seals_self_contained_verified_run(tmp_path: Path) -> None:
    run, oracle, audit, reconciliation, decision = _prepared(tmp_path)

    manifest = seal_distributed_run(
        run_dir=run,
        oracle_dir=oracle,
        layer_audit_dir=audit,
        reconciliation_path=reconciliation,
        decision_report_path=decision,
        machine_metadata_path=run / "machine-metadata.json",
    )
    loaded = load_finalized_run(run)

    row = manifest["views"]["energy_quality"]["rows"][0]
    decision_document = json.loads(decision.read_text("utf-8"))
    for field in (
        "candidate_interval_count",
        "verified_interval_count",
        "comparable_meter_period_count",
        "incomparable_meter_period_count",
        "numeric_discrepancy_meter_period_count",
        "comparison_scope",
        "coverage_limits",
    ):
        assert row[field] == decision_document[field]
    assert manifest == loaded
    assert manifest["replay_run_id"] == "sealed-fixture"
    assert set(manifest["views"]) == set(REQUIRED_VIEWS)
    assert "reports__reconciliation_json" in manifest["artifacts"]
    assert (
        manifest["views"]["energy_quality"]["rows"][0]["monetary_interpretation"]
        == "hypothetical scenarios only; not HKUST financial results"
    )


def test_finalizer_rejects_failed_or_replaced_reconciliation(tmp_path: Path) -> None:
    run, oracle, audit, reconciliation, decision = _prepared(tmp_path)
    value = json.loads(reconciliation.read_text("utf-8"))
    value["status"] = "failed"
    _write_json(reconciliation, value)

    with pytest.raises(ValueError, match="passed reconciliation"):
        seal_distributed_run(
            run_dir=run,
            oracle_dir=oracle,
            layer_audit_dir=audit,
            reconciliation_path=reconciliation,
            decision_report_path=decision,
            machine_metadata_path=run / "machine-metadata.json",
        )


def test_finalizer_rejects_evidence_outside_run_directory(tmp_path: Path) -> None:
    run, oracle, audit, reconciliation, decision = _prepared(tmp_path)
    external = tmp_path / "external-oracle"
    oracle.rename(external)

    with pytest.raises(ValueError, match="inside the run directory"):
        seal_distributed_run(
            run_dir=run,
            oracle_dir=external,
            layer_audit_dir=audit,
            reconciliation_path=reconciliation,
            decision_report_path=decision,
            machine_metadata_path=run / "machine-metadata.json",
        )


def test_finalizer_is_immutable(tmp_path: Path) -> None:
    run, oracle, audit, reconciliation, decision = _prepared(tmp_path)
    (run / "run-manifest.json").write_text("existing", encoding="utf-8")

    with pytest.raises(FileExistsError, match="already sealed"):
        seal_distributed_run(
            run_dir=run,
            oracle_dir=oracle,
            layer_audit_dir=audit,
            reconciliation_path=reconciliation,
            decision_report_path=decision,
            machine_metadata_path=run / "machine-metadata.json",
        )


def test_designated_machine_run_requires_query_and_storage_benchmarks(
    tmp_path: Path,
) -> None:
    run, oracle, audit, reconciliation, decision = _prepared(tmp_path)
    machine_path = run / "machine-metadata.json"
    machine = json.loads(machine_path.read_text("utf-8"))
    machine["execution_context"] = "designated_machine"
    _write_json(machine_path, machine)

    with pytest.raises(ValueError, match="benchmark"):
        seal_distributed_run(
            run_dir=run,
            oracle_dir=oracle,
            layer_audit_dir=audit,
            reconciliation_path=reconciliation,
            decision_report_path=decision,
            machine_metadata_path=machine_path,
        )


@pytest.mark.parametrize("execution_context", ["fixture", "designated_machine"])
def test_benchmarks_are_bound_into_dashboard_view(
    tmp_path: Path,
    execution_context: str,
) -> None:
    run, oracle, audit, reconciliation, decision = _prepared(tmp_path)
    machine_path = run / "machine-metadata.json"
    machine = json.loads(machine_path.read_text("utf-8"))
    machine["execution_context"] = execution_context
    _write_json(machine_path, machine)
    _write_json(
        run / "reports/query-benchmark.json",
        {
            "schema_version": "query-benchmark-v1",
            "execution_policy": "cached_input_full_ordered_json_result_sha256",
            "status": "complete",
            "run_id": "sealed-fixture",
            "gold_manifest_sha256": _hash(run / "gold/gold-manifest.json"),
            "decision_impact_sha256": _hash(decision),
            "parameters": {
                "meter_id": "meter-a",
                "building_id": "building-a",
                "window_start_utc": "2026-01-01T00:00:00Z",
                "window_end_utc": "2026-01-02T00:00:00Z",
            },
            "results": [
                {
                    "query": name,
                    "repetitions": 3,
                    "row_count": 1,
                    "seconds": {"median": 0.1, "minimum": 0.05, "maximum": 0.2},
                    "sql_sha256": "c" * 64,
                    "result_sha256": "d" * 64,
                    "timings_seconds": [0.1, 0.05, 0.2],
                }
                for name in (
                    "meter",
                    "building",
                    "time_window",
                    "quality",
                    "exposure",
                )
            ],
        },
    )
    _write_json(
        run / "storage/storage-benchmark.json",
        {
            "schema_version": "storage-benchmark-v1",
            "status": "complete",
            "run_id": "sealed-fixture",
            "record_count": 3,
            "formats": {
                "ndjson": {
                    "byte_size": 100,
                    "file_count": 1,
                    "sha256": _hash(run / "snapshot/canonical.ndjson"),
                    "write_seconds": None,
                    "relative_to_ndjson": 1.0,
                },
                "parquet_zstd_unpartitioned": {
                    "byte_size": 50,
                    "file_count": 2,
                    "write_seconds": 1.0,
                    "relative_to_ndjson": 0.5,
                },
                "parquet_zstd_partitioned": {
                    "byte_size": 75,
                    "file_count": 3,
                    "partition_columns": ["source_variant", "meter_id"],
                    "write_seconds": 1.5,
                    "relative_to_ndjson": 0.75,
                },
            },
        },
    )

    manifest = seal_distributed_run(
        run_dir=run,
        oracle_dir=oracle,
        layer_audit_dir=audit,
        reconciliation_path=reconciliation,
        decision_report_path=decision,
        machine_metadata_path=machine_path,
    )

    row = manifest["views"]["storage_queries"]["rows"][0]
    assert row["query_results"][0]["query"] == "meter"
    assert row["storage_formats"]["ndjson"]["byte_size"] == 100


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda query, storage: query["results"][0].update(repetitions=2), "query"),
        (
            lambda query, storage: query["results"][0]["seconds"].pop("maximum"),
            "query",
        ),
        (
            lambda query, storage: storage["formats"][
                "parquet_zstd_unpartitioned"
            ].update(relative_to_ndjson=0.75),
            "storage",
        ),
        (lambda query, storage: storage.pop("record_count"), "storage"),
        (lambda query, storage: query.pop("execution_policy"), "query"),
        (lambda query, storage: query.update(execution_policy="count_only"), "query"),
        (lambda query, storage: query["results"][0].pop("result_sha256"), "query"),
        (
            lambda query, storage: query["results"][0].update(result_sha256="bad"),
            "query",
        ),
        (
            lambda query, storage: query["results"][0].update(
                timings_seconds=[0.1, 0.2]
            ),
            "query",
        ),
        (
            lambda query, storage: query["results"][0].update(
                timings_seconds=[0.1, -1, 0.2]
            ),
            "query",
        ),
        (
            lambda query, storage: query["results"][0].update(
                timings_seconds=[0.1, True, 0.2]
            ),
            "query",
        ),
        (
            lambda query, storage: query["results"][0].update(
                timings_seconds=[0.1, float("inf"), 0.2]
            ),
            "query",
        ),
        (
            lambda query, storage: query["results"][0].update(
                timings_seconds=[0.1, 0.1, 0.2]
            ),
            "query",
        ),
    ],
)
@pytest.mark.parametrize("execution_context", ["fixture", "designated_machine"])
def test_seal_rejects_incomplete_or_inconsistent_benchmarks(
    tmp_path: Path, mutation: object, message: str, execution_context: str
) -> None:
    run, oracle, audit, reconciliation, decision = _prepared(tmp_path)
    machine_path = run / "machine-metadata.json"
    machine = json.loads(machine_path.read_text("utf-8"))
    machine["execution_context"] = execution_context
    _write_json(machine_path, machine)
    query = {
        "schema_version": "query-benchmark-v1",
        "execution_policy": "cached_input_full_ordered_json_result_sha256",
        "status": "complete",
        "run_id": "sealed-fixture",
        "gold_manifest_sha256": _hash(run / "gold/gold-manifest.json"),
        "decision_impact_sha256": _hash(decision),
        "parameters": {
            "meter_id": "meter-a",
            "building_id": "building-a",
            "window_start_utc": "2026-01-01T00:00:00Z",
            "window_end_utc": "2026-01-02T00:00:00Z",
        },
        "results": [
            {
                "query": name,
                "repetitions": 3,
                "row_count": 1,
                "seconds": {"median": 0.1, "minimum": 0.05, "maximum": 0.2},
                "sql_sha256": "c" * 64,
                "result_sha256": "d" * 64,
                "timings_seconds": [0.1, 0.05, 0.2],
            }
            for name in ("meter", "building", "time_window", "quality", "exposure")
        ],
    }
    storage = {
        "schema_version": "storage-benchmark-v1",
        "status": "complete",
        "run_id": "sealed-fixture",
        "record_count": 3,
        "formats": {
            "ndjson": {
                "byte_size": 100,
                "file_count": 1,
                "sha256": _hash(run / "snapshot/canonical.ndjson"),
                "write_seconds": None,
                "relative_to_ndjson": 1.0,
            },
            "parquet_zstd_unpartitioned": {
                "byte_size": 50,
                "file_count": 2,
                "write_seconds": 1.0,
                "relative_to_ndjson": 0.5,
            },
            "parquet_zstd_partitioned": {
                "byte_size": 75,
                "file_count": 3,
                "partition_columns": ["source_variant", "meter_id"],
                "write_seconds": 1.5,
                "relative_to_ndjson": 0.75,
            },
        },
    }
    assert callable(mutation)
    mutation(query, storage)  # type: ignore[operator]
    _write_json(run / "reports/query-benchmark.json", query)
    _write_json(run / "storage/storage-benchmark.json", storage)

    with pytest.raises(ValueError, match=message):
        seal_distributed_run(
            run_dir=run,
            oracle_dir=oracle,
            layer_audit_dir=audit,
            reconciliation_path=reconciliation,
            decision_report_path=decision,
            machine_metadata_path=machine_path,
        )


@pytest.mark.parametrize(
    "relative",
    [
        "snapshot/canonical.ndjson",
        "replay/replay-schedule.json",
        "replay/replay-receipt.json",
        "gold/gold_source_events_ndjson.ndjson",
        "gold/gold_aggregates_ndjson.ndjson",
        "oracle/source_records.ndjson",
        "oracle/aggregates.ndjson",
        "layer-audit/silver_candidate_events_ndjson.ndjson",
        "layer-audit/layer_dispositions_ndjson.ndjson",
        "gold/source-events.parquet/part-000.parquet",
        "gold/aggregates.parquet/part-000.parquet",
    ],
)
def test_seal_refuses_bytes_changed_after_reports(
    tmp_path: Path, relative: str
) -> None:
    run, oracle, audit, reconciliation, decision = _prepared(tmp_path)
    original_reports = (reconciliation.read_bytes(), decision.read_bytes())
    path = run / relative
    payload = bytearray(path.read_bytes())
    payload[len(payload) // 2] ^= 1
    path.write_bytes(payload)
    with pytest.raises(ValueError, match="integrity|binding|hash|cannot read|invalid"):
        seal_distributed_run(
            run_dir=run,
            oracle_dir=oracle,
            layer_audit_dir=audit,
            reconciliation_path=reconciliation,
            decision_report_path=decision,
            machine_metadata_path=run / "machine-metadata.json",
        )
    assert not (run / "run-manifest.json").exists()
    assert not (run / "run-manifest.sha256").exists()
    assert original_reports == (reconciliation.read_bytes(), decision.read_bytes())


@pytest.mark.parametrize(
    "relative",
    [
        None,
        "replay/replay-schedule.ndjson",
        "replay/replay-acknowledgements.ndjson",
        "replay/replay-receipt.json",
        "replay/replay-schedule-metadata.json",
    ],
)
def test_seal_validates_streaming_replay_evidence(
    tmp_path: Path, relative: str | None
) -> None:
    run, oracle, audit, reconciliation, decision = _prepared(tmp_path, streaming=True)
    if relative is not None:
        path = run / relative
        payload = bytearray(path.read_bytes())
        payload[len(payload) // 2] ^= 1
        path.write_bytes(payload)
        with pytest.raises(ValueError):
            seal_distributed_run(
                run_dir=run,
                oracle_dir=oracle,
                layer_audit_dir=audit,
                reconciliation_path=reconciliation,
                decision_report_path=decision,
                machine_metadata_path=run / "machine-metadata.json",
            )
        assert not (run / "run-manifest.json").exists()
    else:
        seal_distributed_run(
            run_dir=run,
            oracle_dir=oracle,
            layer_audit_dir=audit,
            reconciliation_path=reconciliation,
            decision_report_path=decision,
            machine_metadata_path=run / "machine-metadata.json",
        )
        assert load_finalized_run(run)["status"] == "finalized"


@pytest.mark.parametrize(
    "field",
    [
        "canonical_ndjson_sha256",
        "silver_candidate_events_sha256",
        "replay_schedule_sha256",
        "replay_receipt_sha256",
    ],
)
def test_seal_checks_reconciliation_data_bindings(tmp_path: Path, field: str) -> None:
    run, oracle, audit, reconciliation, decision = _prepared(tmp_path)
    report = json.loads(reconciliation.read_text("utf-8"))
    report["bindings"][field] = "0" * 64
    _write_json(reconciliation, report)
    business = json.loads(decision.read_text("utf-8"))
    business["reconciliation_sha256"] = _hash(reconciliation)
    _write_json(decision, business)
    with pytest.raises(ValueError, match="binding"):
        seal_distributed_run(
            run_dir=run,
            oracle_dir=oracle,
            layer_audit_dir=audit,
            reconciliation_path=reconciliation,
            decision_report_path=decision,
            machine_metadata_path=run / "machine-metadata.json",
        )
    assert not (run / "run-manifest.json").exists()


def test_loading_sealed_run_is_read_only(tmp_path: Path) -> None:
    run, oracle, audit, reconciliation, decision = _prepared(tmp_path)
    seal_distributed_run(
        run_dir=run,
        oracle_dir=oracle,
        layer_audit_dir=audit,
        reconciliation_path=reconciliation,
        decision_report_path=decision,
        machine_metadata_path=run / "machine-metadata.json",
    )
    before = {
        p.relative_to(run).as_posix(): (p.stat().st_mtime_ns, p.read_bytes())
        for p in run.rglob("*")
        if p.is_file()
    }
    load_finalized_run(run)
    after = {
        p.relative_to(run).as_posix(): (p.stat().st_mtime_ns, p.read_bytes())
        for p in run.rglob("*")
        if p.is_file()
    }
    assert before == after


@pytest.mark.parametrize(
    "relative", ["reports/query-benchmark.json", "storage/storage-benchmark.json"]
)
def test_fixture_seal_requires_both_benchmarks_when_one_exists(
    tmp_path: Path,
    relative: str,
) -> None:
    run, oracle, audit, reconciliation, decision = _prepared(tmp_path)
    _write_json(run / relative, {})
    with pytest.raises(ValueError, match="requires query and storage benchmarks"):
        seal_distributed_run(
            run_dir=run,
            oracle_dir=oracle,
            layer_audit_dir=audit,
            reconciliation_path=reconciliation,
            decision_report_path=decision,
            machine_metadata_path=run / "machine-metadata.json",
        )
    assert not (run / "run-manifest.json").exists()
