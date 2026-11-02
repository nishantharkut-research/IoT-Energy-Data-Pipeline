"""Read-only integrity checks shared by reconciliation, sealing, and queries."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from iot_energy_pipeline.business_report import _artifact, _relative_file, _sha256
from iot_energy_pipeline.replay import load_replay_manifest, load_replay_receipt
from iot_energy_pipeline.schedule import load_schedule
from iot_energy_pipeline.streaming_replay import (
    iter_streaming_deliveries,
    load_streaming_replay_receipt,
    load_streaming_schedule_metadata,
)


def _file(root: Path, relative: object, label: str) -> Path:
    path = _relative_file(root, relative, label)
    if not path.is_file() or any(item.is_symlink() for item in (path, *path.parents)):
        raise ValueError(f"{label} artifact integrity check failed")
    return path


def verify_directory(root: Path, descriptor: object, *, label: str) -> None:
    """Check a Spark directory descriptor using the producer's tree encoding."""
    if not isinstance(descriptor, dict) or set(descriptor) != {
        "directory",
        "file_count",
        "byte_size",
        "tree_sha256",
    }:
        raise ValueError(f"{label} directory integrity descriptor is invalid")
    path = _relative_file(root, descriptor.get("directory"), label)
    if not path.is_dir() or any(item.is_symlink() for item in (path, *path.parents)):
        raise ValueError(f"{label} directory integrity check failed")
    entries: list[dict[str, Any]] = []
    for item in sorted(path.rglob("*"), key=lambda p: p.relative_to(path).as_posix()):
        if item.is_symlink():
            raise ValueError(f"{label} directory integrity check failed")
        if item.is_file():
            entries.append(
                {
                    "relative_path": item.relative_to(path).as_posix(),
                    "byte_size": item.stat().st_size,
                    "sha256": _sha256(item),
                }
            )
    payload = json.dumps(
        entries, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")
    if (
        not entries
        or type(descriptor["file_count"]) is not int
        or type(descriptor["byte_size"]) is not int
        or descriptor["file_count"] != len(entries)
        or descriptor["byte_size"] != sum(entry["byte_size"] for entry in entries)
        or descriptor["tree_sha256"] != hashlib.sha256(payload).hexdigest()
    ):
        raise ValueError(f"{label} directory integrity check failed")


def verify_gold_artifacts(gold_dir: Path, manifest: dict[str, Any]) -> None:
    """Verify both Gold NDJSON exports and both queryable Parquet trees."""
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, dict):
        raise ValueError("Gold artifact integrity registry is invalid")
    for name in ("gold_source_events_ndjson", "gold_aggregates_ndjson"):
        _artifact(gold_dir, artifacts.get(name), path_field="file", label=name)
    for name, directory in (
        ("source_events_parquet", "source-events.parquet"),
        ("aggregates_parquet", "aggregates.parquet"),
    ):
        descriptor = artifacts.get(name)
        if not isinstance(descriptor, dict) or descriptor.get("directory") != directory:
            raise ValueError(f"{name} directory integrity binding mismatch")
        verify_directory(gold_dir, descriptor, label=name)


def verify_replay_evidence(run_dir: Path, plan: dict[str, Any]) -> dict[str, str]:
    """Load validated replay evidence and return byte bindings for new reports."""
    canonical = _file(run_dir, plan.get("canonical_ndjson_path"), "canonical NDJSON")
    manifest_path = _file(run_dir, plan.get("replay_manifest_path"), "replay manifest")
    manifest = load_replay_manifest(manifest_path)
    if (
        manifest.sha256() != plan.get("replay_manifest_hash")
        or manifest.replay_run_id != plan.get("run_id")
        or manifest.snapshot_hash != _sha256(canonical)
        or manifest.snapshot_hash != plan.get("canonical_ndjson_sha256")
        or manifest.schedule_hash != plan.get("schedule_hash")
        or manifest.requested_event_count != plan.get("canonical_event_count")
        or manifest.expected_delivery_count != plan.get("expected_delivery_count")
        or manifest.expected_terminal_count != plan.get("expected_terminal_count")
    ):
        raise ValueError("canonical or replay manifest binding mismatch")
    schedule_path = _file(run_dir, plan.get("schedule_path"), "replay schedule")
    receipt_path = _file(run_dir, "replay/replay-receipt.json", "replay receipt")
    bindings = {
        "canonical_ndjson_sha256": _sha256(canonical),
        "replay_schedule_sha256": _sha256(schedule_path),
        "replay_receipt_sha256": _sha256(receipt_path),
    }
    if plan.get("schedule_format") == "delivery-ndjson-v2":
        metadata_path = _file(
            run_dir, plan.get("schedule_metadata_path"), "schedule metadata"
        )
        if _sha256(metadata_path) != plan.get("schedule_metadata_sha256"):
            raise ValueError("schedule metadata binding mismatch")
        metadata = load_streaming_schedule_metadata(
            metadata_path, schedule_path=schedule_path
        )
        if (
            metadata.run_id != manifest.replay_run_id
            or metadata.schedule_sha256 != manifest.schedule_hash
            or metadata.partition_count != manifest.partition_count
            or metadata.delivery_count != manifest.expected_delivery_count
        ):
            raise ValueError("replay schedule binding mismatch")
        acknowledgements = _file(
            run_dir, "replay/replay-acknowledgements.ndjson", "acknowledgement ledger"
        )
        receipt = load_streaming_replay_receipt(
            receipt_path, acknowledgement_path=acknowledgements
        )
        with acknowledgements.open("r", encoding="utf-8") as stream:
            for delivery, line in zip(
                iter_streaming_deliveries(schedule_path, metadata), stream, strict=True
            ):
                acknowledgement = json.loads(line)
                if (
                    acknowledgement["delivery_id"] != delivery.delivery_id
                    or acknowledgement["partition"] != delivery.partition
                ):
                    raise ValueError("replay receipt schedule binding mismatch")
        bindings["replay_acknowledgements_sha256"] = _sha256(acknowledgements)
    else:
        schedule = load_schedule(schedule_path)
        if (
            schedule.run_id != manifest.replay_run_id
            or schedule.schedule_hash != manifest.schedule_hash
            or schedule.partition_count != manifest.partition_count
            or len(schedule.deliveries) != manifest.expected_delivery_count
        ):
            raise ValueError("replay schedule binding mismatch")
        loaded = load_replay_receipt(receipt_path)
        receipt = asdict(loaded)
        expected = {d.delivery_id: d.partition for d in schedule.deliveries}
        actual = {a.delivery_id: a.partition for a in loaded.acknowledgements}
        if actual != expected or len(actual) != len(loaded.acknowledgements):
            raise ValueError("replay receipt schedule binding mismatch")
    if (
        receipt.get("replay_run_id") != manifest.replay_run_id
        or receipt.get("replay_manifest_hash") != manifest.sha256()
        or receipt.get("schedule_hash") != manifest.schedule_hash
        or receipt.get("expected_delivery_count") != manifest.expected_delivery_count
        or receipt.get("acknowledged_delivery_count")
        != manifest.expected_delivery_count
        or set(receipt["terminal_offsets"])
        != {str(p) for p in range(manifest.partition_count)}
    ):
        raise ValueError("replay receipt binding mismatch")
    return bindings


def verify_export_artifacts(
    run_dir: Path,
    oracle_dir: Path,
    layer_audit_dir: Path,
    gold: dict[str, Any],
    oracle: dict[str, Any],
    layers: dict[str, Any],
) -> str:
    """Verify originating descriptors; return the Silver candidate digest."""
    verify_gold_artifacts(run_dir / "gold", gold)
    for root, registry, field, names in (
        (
            oracle_dir,
            oracle.get("outputs"),
            "local_file",
            ("source_records", "aggregates"),
        ),
        (
            layer_audit_dir,
            layers.get("artifacts"),
            "file",
            ("silver_candidate_events_ndjson", "layer_dispositions_ndjson"),
        ),
    ):
        if not isinstance(registry, dict):
            raise ValueError("export artifact integrity registry is invalid")
        for name in names:
            _artifact(root, registry.get(name), path_field=field, label=name)
    candidate, _, _ = _artifact(
        layer_audit_dir,
        layers["artifacts"]["silver_candidate_events_ndjson"],
        path_field="file",
        label="Silver candidate events",
    )
    return _sha256(candidate)
