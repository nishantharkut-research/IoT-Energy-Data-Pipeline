"""Bound, portable summaries; never substitutes for the sealed-run loader."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

INPUTS = {
    "results": "docs/results/final/final-results.json",
    "scope": "docs/results/final/final-coursework-scope.json",
    "plan": "docs/results/final/experiment-plan.json",
    "source_audit": "docs/results/source-audit-2026-10-27.md",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _source_counts(text: str) -> dict[str, dict[str, int]]:
    counts = {}
    for line in text.splitlines():
        match = re.fullmatch(r"\| ([^|]+?) \| ([\d,]+) \| ([\d,]+) \|", line)
        if match:
            name, raw, clean = match.groups()
            counts[name] = {
                "raw": int(raw.replace(",", "")),
                "clean": int(clean.replace(",", "")),
            }
    required = {
        "Workbooks",
        "Physical data rows",
        "Finite numeric readings",
        "Missing numeric cells",
        "Negative readings",
        "Ordered numeric decreases",
        "Duplicate decoded timestamps",
        "Out-of-order timestamps",
    }
    if not required <= counts.keys():
        raise ValueError("source audit is missing required counters")
    for variant in ("raw", "clean"):
        if counts["Physical data rows"][variant] != (
            counts["Finite numeric readings"][variant]
            + counts["Missing numeric cells"][variant]
        ):
            raise ValueError("source counter conservation failed")
    return counts


def load_submission_evidence(root: Path) -> dict[str, Any]:
    """Validate bounded saved summaries, with no dataset or runtime directory access."""
    index_path = root / "docs/results/submission/evidence-index.json"
    if not index_path.is_file():
        raise ValueError("submission evidence index is missing")
    index = json.loads(index_path.read_bytes())
    if index.get("schema_version") != "submission-evidence-index-v1":
        raise ValueError("unsupported submission evidence index")
    documents: dict[str, Any] = {}
    for name, relative in INPUTS.items():
        path = root / relative
        if not path.is_file() or path.is_symlink():
            raise ValueError(f"evidence missing or unsafe: {relative}")
        entry = index.get("inputs", {}).get(name, {})
        if (
            entry.get("path") != relative
            or path.stat().st_size != entry.get("byte_size")
            or sha256(path) != entry.get("sha256")
        ):
            raise ValueError(f"evidence binding failed: {relative}")
        documents[name] = (
            path.read_text(encoding="utf-8-sig")
            if name == "source_audit"
            else json.loads(path.read_bytes())
        )
    results, scope, plan = (documents[n] for n in ("results", "scope", "plan"))
    if (
        results.get("schema_version") != "coursework-closure-v1"
        or results.get("status") != "complete_for_final_scope"
        or scope.get("status") != "all_in_scope_runs_sealed"
    ):
        raise ValueError("saved experiment scope is incomplete")
    if (
        results["final_scope_sha256"] != index["inputs"]["scope"]["sha256"]
        or results["original_plan_sha256"] != index["inputs"]["plan"]["sha256"]
        or scope["original_plan_sha256"] != results["original_plan_sha256"]
    ):
        raise ValueError("original scope/plan binding failed")
    runs = results["runs"]
    ids = [r["run_id"] for r in runs]
    expected = {r["run_id"]: r for r in scope["completed_runs"]}
    planned = {r["run_id"] for r in plan["runs"]} - set(scope["excluded_runs"])
    if (
        len(ids) != 15
        or len(set(ids)) != len(ids)
        or set(ids) != expected.keys()
        or set(ids) != planned
    ):
        raise ValueError("run identities do not match the completed scope")
    for run in runs:
        if (
            run["status"] != "finalized"
            or run["manifest_sha256"] != expected[run["run_id"]]["run_manifest_sha256"]
        ):
            raise ValueError("run finalization summary binding failed")
        for key in ("source_comparison", "aggregate_comparison"):
            comparison = run[key]
            if (
                comparison["errors"]
                or not comparison["exact_fields"]
                or comparison["spark_record_count"] != comparison["hadoop_record_count"]
            ):
                raise ValueError("saved reconciliation does not agree")
        if run["source_records"] != run["source_comparison"]["spark_record_count"]:
            raise ValueError("saved source count mismatch")
        layer = run["layer_counts"]
        if (
            layer["bronze_deliveries"]
            != layer["parsed_valid_deliveries"] + layer["quarantine_deliveries"]
            or layer["parsed_valid_deliveries"]
            != layer["silver_deliveries"]
            + layer["duplicate_valid_deliveries"]
            + layer["late_valid_deliveries"]
        ):
            raise ValueError("delivery conservation failed")
    return {
        "results": results,
        "scope": scope,
        "plan": plan,
        "source_counts": _source_counts(documents["source_audit"]),
        "index": index,
        "runtime_reverified": False,
    }
