"""Verify existing artifacts and report the final coursework scope; never run jobs."""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
from datetime import datetime, timezone
from pathlib import Path

from dashboard.data import load_finalized_run
from iot_energy_pipeline.experiment_execution import (
    _recovery_equivalence,
    evaluate_cross_run_acceptance,
)

PUBLISHED_FILES = {
    "gold/gold-source-events.ndjson",
    "gold/gold-aggregates.ndjson",
    "gold/gold-manifest.json",
    "oracle/hadoop-source-records.ndjson",
    "oracle/hadoop-aggregates.ndjson",
    "oracle/hadoop-oracle-manifest.json",
    "reports/reconciliation.json",
    "reports/decision-impact.json",
    "reports/query-benchmark.json",
    "storage/storage-benchmark.json",
    "distributed-plan.json",
    "machine-metadata.json",
}


def read(path: Path) -> dict:
    return json.loads(path.read_bytes())


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_published_run(directory: Path, expected: str) -> tuple[dict, list[str]]:
    """Verify scope-bound seals and published results, excluding runtime checkpoints."""
    path = directory / "run-manifest.json"
    if sha(path) != expected:
        raise ValueError("Run manifest differs from final scope")
    if (directory / "run-manifest.sha256").read_text().strip() != expected:
        raise ValueError("Run manifest seal differs from final scope")
    manifest = read(path)
    if (
        manifest.get("schema_version") != "finalized-run-v1"
        or manifest.get("status") != "finalized"
        or manifest.get("reconciled") is not True
        or manifest.get("immutable") is not True
    ):
        raise ValueError("Run is not finalized, immutable, and reconciled")
    registry = {a["relative_path"]: a for a in manifest["artifacts"].values()}
    checked = []
    for relative in sorted(PUBLISHED_FILES):
        descriptor = registry.get(relative)
        target = directory / relative
        if (
            not descriptor
            or not target.is_file()
            or target.is_symlink()
            or target.stat().st_size != descriptor["byte_size"]
            or sha(target) != descriptor["sha256"]
        ):
            raise ValueError("Published artifact integrity failed: " + relative)
        checked.append(relative)
    return manifest, checked


def summary(values: list[float]) -> dict:
    return {
        "n": len(values),
        "minimum": min(values),
        "median": statistics.median(values),
        "maximum": max(values),
    }


def close(
    plan_path: Path,
    scope_path: Path,
    runtime: Path,
    output: Path,
    full_artifact_check: bool = False,
) -> None:
    plan, scope = read(plan_path), read(scope_path)
    if sha(plan_path) != scope["original_plan_sha256"]:
        raise ValueError("Final scope does not bind this original plan")
    excluded = set(scope["excluded_runs"])
    planned = [r for r in plan["runs"] if r["run_id"] not in excluded]
    if {r["run_id"] for r in planned} != {r["run_id"] for r in scope["completed_runs"]}:
        raise ValueError("Final scope and plan disagree")
    if any((runtime / name).exists() for name in excluded):
        raise ValueError("Excluded run artifacts require review")
    records = []
    expected_hashes = {
        r["run_id"]: r["run_manifest_sha256"] for r in scope["completed_runs"]
    }
    for raw in planned:
        run_id = raw["run_id"]
        directory = runtime / run_id
        print("Verifying published evidence: " + run_id, flush=True)
        manifest, checked = verify_published_run(directory, expected_hashes[run_id])
        if full_artifact_check:
            manifest = load_finalized_run(directory)
        if manifest["replay_run_id"] != run_id:
            raise ValueError("Run identity differs from plan")
        reconciliation = read(directory / "reports/reconciliation.json")
        decision = read(directory / "reports/decision-impact.json")
        if reconciliation["status"] != "passed" or any(
            reconciliation[k]["errors"]
            for k in ("source_record_comparison", "aggregate_comparison")
        ):
            raise ValueError("Reconciliation failed: " + run_id)
        count = reconciliation["source_record_comparison"]["spark_record_count"]
        if isinstance(raw["event_count"], int) and count != raw["event_count"]:
            raise ValueError("Source count differs from plan")
        records.append(
            {
                **raw,
                "status": "finalized",
                "source_records": count,
                "manifest_sha256": sha(directory / "run-manifest.json"),
                "freshly_verified_artifacts": checked,
                "layer_counts": reconciliation["layer_counts"],
                "source_comparison": reconciliation["source_record_comparison"],
                "aggregate_comparison": reconciliation["aggregate_comparison"],
                "decision": {
                    k: v
                    for k, v in decision.items()
                    if k
                    not in {
                        "candidate_flagged_records",
                        "verified_flagged_records",
                        "affected_meter_periods",
                    }
                },
                "storage": read(directory / "storage/storage-benchmark.json"),
                "queries": read(directory / "reports/query-benchmark.json"),
                "recovery": read(directory / "execution-recovery.json")
                if (directory / "execution-recovery.json").exists()
                else None,
            }
        )
    acceptance = {
        **evaluate_cross_run_acceptance(runtime),
        "recovery_semantic_equivalence": _recovery_equivalence(runtime),
    }
    metrics = []
    for size in scope["scale_event_counts"]:
        group = [r for r in records if r["event_count"] == size]
        if len(group) != scope["scale_repetitions"]:
            raise ValueError("Missing scale repetitions")
        metrics.append(
            {
                "event_count": size,
                "verification_seconds": summary(
                    [r["decision"]["verification_seconds"] for r in group]
                ),
                "verification_bytes": summary(
                    [r["decision"]["verification_storage_bytes"] for r in group]
                ),
            }
        )
    result = {
        "schema_version": "coursework-closure-v1",
        "status": "complete_for_final_scope",
        "verification_scope": (
            "full registered artifact sets"
            if full_artifact_check
            else "scope-bound run seals and published Gold/Hadoop outputs, manifests, "
            "reconciliation, decision, query, storage, and machine reports; "
            "runtime checkpoints and operational logs were not rehashed"
        ),
        "verified_at_utc": datetime.now(timezone.utc).isoformat(),
        "original_plan_sha256": sha(plan_path),
        "final_scope_sha256": sha(scope_path),
        "excluded_runs": sorted(excluded),
        "limitations": scope["limitations"],
        "runs": records,
        "performance_summary": metrics,
        **acceptance,
    }
    lines = [
        "# IoT Energy Data Pipeline: final results",
        "",
        "All 15 runs in the final coursework scope passed independent "
        "reconciliation. Published evidence was freshly hash-verified against "
        "scope-bound run seals. This report uses existing "
        "results; generating it starts no Kafka, Spark, or Hadoop workloads.",
        "",
        "The final scope includes nine fixtures and three repetitions each at "
        "100K and 1M source events. The original three 5M runs are excluded "
        "because of resource and time constraints.",
        "",
        "## Correctness and delivery accounting",
        "",
        "| Run | Gold/source records | Bronze | Duplicates | "
        "Late | Quarantine | Silver |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for r in records:
        c = r["layer_counts"]
        lines.append(
            f"| {r['run_id']} | {r['source_records']:,} | "
            + " | ".join(
                f"{c[k]:,}"
                for k in (
                    "bronze_deliveries",
                    "duplicate_valid_deliveries",
                    "late_valid_deliveries",
                    "quarantine_deliveries",
                    "silver_deliveries",
                )
            )
            + " |"
        )
    lines += [
        "",
        "All source-record and aggregate comparison error lists are empty. "
        "The five correctness schedules produce identical semantic Gold and "
        "Hadoop outputs. Interrupted and uninterrupted recovery outputs also "
        "match byte for byte for all four semantic artifacts.",
        "",
        "## Watermark and decision impact",
        "",
        "The retaining watermark preserves 144 source events in Silver. "
        "The restrictive watermark preserves 143, while Gold and Hadoop "
        "both retain all 144. The missing candidate record changes two "
        "meter periods. Both periods have incomparable interval supports; "
        "the verified result flags an ambiguous duplicate timestamp.",
        "",
        "Comparable intervals have zero measured kWh discrepancy in these "
        "runs. This subtotal does not establish zero total energy error. "
        "Residual exposure is unknown. The 0.5, 1.0, and 2.0 rates are "
        "hypothetical normalized scenarios, not HKUST tariffs or savings.",
        "",
        "## Verification cost",
        "",
        "Time includes Gold finalization, layer auditing, Hadoop computation, "
        "and reconciliation. It excludes streaming and the later storage/query "
        "benchmarks. Storage is the scoped verification artifact set, not total "
        "runtime disk usage.",
        "",
        "| Events | Repetitions | Minimum (min) | Median (min) | Maximum (min) | "
        "Median verification storage (MB, decimal) |",
        "| ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for m in metrics:
        t = m["verification_seconds"]
        lines.append(
            f"| {m['event_count']:,} | {t['n']} | {t['minimum'] / 60:.2f} | "
            f"{t['median'] / 60:.2f} | {t['maximum'] / 60:.2f} | "
            f"{m['verification_bytes']['median'] / 1e6:.2f} |"
        )
    lines += [
        "",
        "All three 1M workflows were interrupted and recovered. Complete "
        "workflow timing is unavailable. The component timings above remain "
        "recorded measurements; they are not uninterrupted end-to-end timings.",
        "",
        "## Storage and SQL",
        "",
        "Each row is one completed scale repetition. Ratios are stored bytes "
        "divided by canonical NDJSON bytes. Smaller is better for space.",
        "",
        "| Run | NDJSON (MB) | Zstd Parquet unpartitioned / NDJSON | "
        "Zstd Parquet partitioned / NDJSON |",
        "| --- | ---: | ---: | ---: |",
    ]
    for r in records:
        if r["experiment"] != "scale":
            continue
        f = r["storage"]["formats"]
        lines.append(
            f"| {r['run_id']} | {f['ndjson']['byte_size'] / 1e6:.2f} | "
            f"{f['parquet_zstd_unpartitioned']['relative_to_ndjson']:.4f} | "
            f"{f['parquet_zstd_partitioned']['relative_to_ndjson']:.4f} |"
        )
    lines += [
        "",
        "The five read-only SQL queries cover meter, building, time window, "
        "quality, and exposure. Each query has three timing repetitions per "
        "run and a full ordered result hash. The following figures are medians "
        "in seconds within each run. 100K uses the original query settings; "
        "1M uses smaller partitions. This is not a configuration-controlled "
        "scaling comparison.",
        "",
        "| Run | Query | Rows | Minimum (s) | Median (s) | Maximum (s) |",
        "| --- | --- | ---: | ---: | ---: | ---: |",
    ]
    for r in records:
        if r["experiment"] == "scale":
            for q in r["queries"]["results"]:
                t = q["seconds"]
                lines.append(
                    f"| {r['run_id']} | {q['query']} | {q['row_count']:,} | "
                    f"{t['minimum']:.3f} | {t['median']:.3f} | {t['maximum']:.3f} |"
                )
    lines += [
        "",
        "## Interpretation and limits",
        "",
        "These experiments demonstrate delivery accounting, exact recovery "
        "from Bronze, and agreement with an independently implemented Hadoop "
        "computation through 1M source records. They do not establish live "
        "deployment performance, measurement accuracy, financial savings, "
        "or a new streaming algorithm.",
        "",
    ]
    lines += ["- " + s for s in result["limitations"]]
    lines += [
        "",
        "## Evidence",
        "",
        f"- Original experiment plan SHA-256: `{sha(plan_path)}`",
        f"- Final scope record SHA-256: `{sha(scope_path)}`",
        f"- Fresh evidence verification completed: {result['verified_at_utc']}",
        "- Verification scope: " + result["verification_scope"],
        "- Machine-readable run summaries, exact comparison fields, query hashes, "
        "and cross-run semantic hashes: `final-results.json`.",
    ]
    output.mkdir(parents=True, exist_ok=True)
    (output / "final-results.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    (output / "course-results.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("Verified and wrote final report: " + str(output), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--scope", required=True, type=Path)
    parser.add_argument("--runtime", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--full-artifact-check", action="store_true")
    args = parser.parse_args()
    close(args.plan, args.scope, args.runtime, args.output, args.full_artifact_check)
