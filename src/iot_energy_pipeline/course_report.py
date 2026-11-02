"""Generate the measured coursework report only from sealed experiment results."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping

from dashboard.data import load_finalized_run
from iot_energy_pipeline.experiment_execution import (
    _performance_summary,
    _recovery_equivalence,
    _validate_execution_plan,
    evaluate_cross_run_acceptance,
    load_workflow_receipt,
)
from iot_energy_pipeline.machine_metadata import validate_machine_metadata


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_object(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read {label}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    return value


def _display_count(value: object) -> str:
    return f"{value:,}" if isinstance(value, int) else str(value)


def _validate_run_configuration(
    planned: Mapping[str, Any],
    distributed: Mapping[str, Any],
    gold: Mapping[str, Any],
    replay: Mapping[str, Any],
) -> None:
    count = distributed.get("canonical_event_count")
    fields = (
        "run_id",
        "fault",
        "seed",
        "partition_count",
        "watermark",
        "max_offsets_per_trigger",
    )
    if (
        any(distributed.get(field) != planned[field] for field in fields)
        or isinstance(count, bool)
        or not isinstance(count, int)
        or count < 1
        or (planned["event_count"] != "fixture" and count != planned["event_count"])
        or gold.get("source_coverage_count") != count
        or replay.get("requested_event_count") != count
        or replay.get("repetition") != planned["repetition"]
    ):
        raise ValueError(
            "executed run configuration differs from the planned measurement"
        )


def render_course_report(
    results: Mapping[str, Any], decisions: Mapping[str, Mapping[str, Any]]
) -> str:
    """Render a concise report from already verified result documents."""

    if results.get("status") != "complete":
        raise ValueError("course report requires complete experiment results")
    runs = results.get("runs")
    performance = results.get("performance_summary")
    correctness = results.get("correctness_semantic_equivalence")
    recovery = results.get("recovery_semantic_equivalence")
    watermark = results.get("watermark_effect")
    if (
        not isinstance(runs, list)
        or not isinstance(performance, list)
        or not isinstance(correctness, dict)
        or not isinstance(recovery, dict)
        or not isinstance(watermark, dict)
    ):
        raise ValueError("complete experiment results are structurally invalid")
    if watermark.get("candidate_difference_exposed") is not True:
        raise ValueError(
            "complete results must expose the restrictive watermark effect"
        )
    lines = [
        "# Auditable IoT Energy Data Pipeline — Course Results",
        "",
        "This report is generated only from sealed, reconciled runs. The HKUST "
        "dataset is public source telemetry; the project is not affiliated with HKUST.",
        "",
        "## Evidence bindings",
        "",
        "| Artifact | SHA-256 |",
        "| --- | --- |",
        f"| Experiment plan | `{results.get('experiment_plan_sha256')}` |",
        (
            "| Canonical snapshot manifest | "
            f"`{results.get('snapshot_manifest_sha256')}` |"
        ),
        f"| Machine metadata | `{results.get('machine_metadata_sha256')}` |",
        "",
        "## Finalized runs",
        "",
        "| Run | Family | Events | Workflow before sealing (s) | Status |",
        "| --- | --- | ---: | ---: | --- |",
    ]
    for run in runs:
        if not isinstance(run, dict):
            raise ValueError("complete experiment results contain an invalid run")
        lines.append(
            f"| {run.get('run_id')} | {run.get('experiment')} | "
            f"{_display_count(run.get('event_count'))} | "
            f"{float(run.get('workflow_seconds', 0)):.6f} | {run.get('status')} |"
        )
    lines.extend(
        [
            "",
            "## Scale performance",
            "",
            "Workflow timing covers run preparation through query benchmarking; "
            "it excludes service startup, sealing, and post-seal validation.",
            "",
            "Every scale cell is reported as median, minimum, and maximum over "
            "three clean repetitions.",
            "",
            "| Events | Metric | Median | Minimum | Maximum |",
            "| ---: | --- | ---: | ---: | ---: |",
        ]
    )
    for group in performance:
        if not isinstance(group, dict) or not isinstance(group.get("metrics"), dict):
            raise ValueError("performance summary is invalid")
        for metric, summary in group["metrics"].items():
            if not isinstance(summary, dict):
                raise ValueError("performance metric summary is invalid")
            lines.append(
                f"| {_display_count(group.get('event_count'))} | {metric} | "
                f"{summary.get('median')} | {summary.get('minimum')} | "
                f"{summary.get('maximum')} |"
            )
    lines.extend(
        [
            "",
            "## Correctness and recovery",
            "",
            "| Gate | Result |",
            "| --- | --- |",
            "| Every published run | Spark Gold and both Hadoop oracle outputs "
            "reconciled exactly |",
            f"| Fault schedules | {correctness.get('status')} |",
            f"| Recovery records | {recovery.get('status')} |",
            "| Restrictive watermark | candidate difference exposed |",
            f"| Watermark exact Gold/oracle | {watermark.get('gold_status')} |",
            "",
            "## Decision impact",
            "",
            "| Run | Affected meter-periods | Incomparable periods | "
            "Comparable kWh discrepancy | "
            "Verification seconds |",
            "| --- | ---: | ---: | ---: | ---: |",
        ]
    )
    for run_id in sorted(decisions):
        decision = decisions[run_id]
        lines.append(
            f"| {run_id} | {decision.get('affected_meter_period_count')} | "
            f"{decision.get('incomparable_meter_period_count')} | "
            f"{decision.get('absolute_kwh_discrepancy')} | "
            f"{decision.get('verification_seconds')} |"
        )
    lines.extend(
        [
            "",
            (
                "Rates 0.5, 1.0, and 2.0 are normalized hypothetical scenarios. "
                "Every monetary value is a scenario only; it is not an HKUST "
                "financial result."
            ),
            "Consumption differences and tariff subtotals cover identical interval "
            "supports only. Unavailable or unequal supports are reported separately; "
            "residual exposure remains unknown.",
            "",
            "## Interpretation limits",
            "",
            (
                "The measurements apply to the declared dataset snapshot, fault "
                "schedules, "
                "software versions, and machine. They do not establish universal "
                "exactly-once processing, live campus operation, energy savings, or "
                "production readiness."
            ),
            "",
        ]
    )
    return "\n".join(lines)


def generate_course_report(
    *, experiment_results_path: Path, runtime_root: Path, output: Path
) -> str:
    """Verify every sealed run referenced by results and write immutable Markdown."""

    if output.exists():
        raise FileExistsError(f"immutable course report already exists: {output}")
    results = _json_object(experiment_results_path, "experiment results")
    if results.get("status") != "complete" or not isinstance(results.get("runs"), list):
        raise ValueError("course report requires complete experiment results")
    evidence = runtime_root / "_experiment-evidence"
    bindings: dict[str, str] = {}
    documents: dict[str, dict[str, Any]] = {}
    for label, filename in (
        ("experiment_plan_sha256", "experiment-plan.json"),
        ("machine_metadata_sha256", "machine-metadata.json"),
        ("snapshot_manifest_sha256", "snapshot-manifest.json"),
    ):
        path = evidence / filename
        if (
            not path.is_file()
            or path.is_symlink()
            or results.get(label) != _sha256(path)
        ):
            raise ValueError(f"experiment evidence binding mismatch: {filename}")
        bindings[label] = _sha256(path)
        documents[filename] = _json_object(path, filename)
    plan = documents["experiment-plan.json"]
    machine = documents["machine-metadata.json"]
    snapshot = documents["snapshot-manifest.json"]
    validate_machine_metadata(machine)
    if machine.get("execution_context") != "designated_machine":
        raise ValueError("experiment evidence requires designated-machine metadata")
    descriptor = snapshot.get("artifacts", {}).get("canonical_ndjson", {})
    full_count = descriptor.get("record_count")
    if (
        snapshot.get("status") != "complete"
        or snapshot.get("schema_version") != "snapshot-manifest-v1"
        or isinstance(full_count, bool)
        or not isinstance(full_count, int)
        or full_count < 1
        or plan.get("machine_metadata_sha256") != bindings["machine_metadata_sha256"]
        or plan.get("snapshot_manifest_sha256") != bindings["snapshot_manifest_sha256"]
        or plan.get("canonical_ndjson_sha256") != descriptor.get("sha256")
    ):
        raise ValueError("experiment plan/source evidence binding mismatch")
    expected = _validate_execution_plan(
        plan,
        repository=Path(__file__).resolve().parents[2],
        full_event_count=full_count,
    )
    runs = results["runs"]
    if (
        results.get("schema_version") != "experiment-results-v1"
        or len(runs) != len(expected)
        or results.get("monetary_interpretation")
        != "hypothetical scenarios; not HKUST results"
    ):
        raise ValueError("experiment results do not cover the complete fixed matrix")
    decisions: dict[str, dict[str, Any]] = {}
    for run, planned in zip(runs, expected, strict=True):
        if not isinstance(run, dict) or not isinstance(run.get("run_id"), str):
            raise ValueError("experiment results contain an invalid run")
        if (
            any(
                run.get(field) != planned[field]
                for field in ("run_id", "experiment", "event_count", "repetition")
            )
            or run.get("status") != "finalized"
        ):
            raise ValueError("experiment result run differs from the fixed matrix")
        run_id = run["run_id"]
        run_dir = runtime_root / run_id
        loaded = load_finalized_run(run_dir)
        if loaded.get("replay_run_id") != run_id or run.get(
            "run_manifest_sha256"
        ) != _sha256(run_dir / "run-manifest.json"):
            raise ValueError(f"sealed run binding mismatch: {run_id}")
        if (
            run.get("artifact_count") != len(loaded["artifacts"])
            or _sha256(run_dir / "machine-metadata.json")
            != bindings["machine_metadata_sha256"]
            or run.get("workflow_seconds")
            != load_workflow_receipt(run_dir, run_id=run_id, bindings=bindings)[
                "workflow_seconds"
            ]
        ):
            raise ValueError(f"sealed run measurement binding mismatch: {run_id}")
        distributed = _json_object(
            run_dir / "distributed-plan.json", "distributed plan"
        )
        _validate_run_configuration(
            planned,
            distributed,
            _json_object(run_dir / "gold/gold-manifest.json", "Gold manifest"),
            _json_object(run_dir / "replay/replay-manifest.json", "replay manifest"),
        )
        if planned["experiment"] == "scale":
            if (
                distributed.get("source_snapshot_manifest_sha256")
                != bindings["snapshot_manifest_sha256"]
                or distributed.get("source_snapshot_sha256") != descriptor["sha256"]
            ):
                raise ValueError(
                    f"sealed run source snapshot binding mismatch: {run_id}"
                )
        decision = _json_object(
            run_dir / "reports/decision-impact.json", "decision-impact report"
        )
        if decision.get("status") != "verified" or decision.get("run_id") != run_id:
            raise ValueError(f"decision-impact report is not verified: {run_id}")
        decisions[run_id] = decision
    cross_run = evaluate_cross_run_acceptance(runtime_root)
    if (
        results.get("performance_summary") != _performance_summary(runs, runtime_root)
        or results.get("recovery_semantic_equivalence")
        != _recovery_equivalence(runtime_root)
        or results.get("correctness_semantic_equivalence")
        != cross_run["correctness_semantic_equivalence"]
        or results.get("watermark_effect") != cross_run["watermark_effect"]
    ):
        raise ValueError("experiment summaries disagree with sealed run evidence")
    report = render_course_report(results, decisions)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(report)
        stream.flush()
        os.fsync(stream.fileno())
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--experiment-results", type=Path, required=True)
    parser.add_argument("--runtime-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    generate_course_report(
        experiment_results_path=args.experiment_results,
        runtime_root=args.runtime_root,
        output=args.output,
    )
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
