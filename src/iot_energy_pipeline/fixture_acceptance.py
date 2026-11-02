"""Execute and seal the nine Docker fixture cases without a source snapshot.

Run with ``python -m iot_energy_pipeline.fixture_acceptance --help``. This is
actual execution, not the local fixture simulator. Unit tests replace job
execution; only a successful real invocation establishes distributed acceptance.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import re
import sys
from pathlib import Path
from typing import Any

from dashboard.data import load_finalized_run
from iot_energy_pipeline.experiment_execution import (
    EXECUTION_CONFIRMATION,
    CommandSpec,
    _prepare_run,
    _recovery_equivalence,
    _run_command,
    _sha256,
    _write_new,
    build_processing_commands,
    evaluate_cross_run_acceptance,
    require_execution_confirmation,
)
from iot_energy_pipeline.experiment_plan import build_planned_runs
from iot_energy_pipeline.machine_metadata import validate_machine_metadata
from iot_energy_pipeline.reports import load_experiment_matrix

_LOGGER = logging.getLogger(__name__)

_PROOF_ARTIFACTS = (
    "gold/gold-manifest.json",
    "oracle/hadoop-oracle-manifest.json",
    "layer-audit/layer-audit-manifest.json",
    "reports/reconciliation.json",
    "reports/decision-impact.json",
    "storage/storage-benchmark.json",
    "reports/query-benchmark.json",
)


def _fresh_runtime(repository: Path, requested: Path | None) -> Path:
    if requested is None:
        configured = os.environ.get("PIPELINE_RUNTIME_DIR")
        if not configured:
            raise ValueError("provide --runtime-root or PIPELINE_RUNTIME_DIR")
        requested = Path(configured)
    if not requested.is_absolute():
        requested = repository / requested
    base = (repository / "reports/runtime").resolve(strict=False)
    root = requested.resolve(strict=False)
    try:
        base.relative_to(repository)
        relative = root.relative_to(base)
        if not relative.parts:
            raise ValueError("runtime root equals its parent")
    except ValueError as exc:
        raise ValueError(
            "runtime root must be strictly below repository reports/runtime"
        ) from exc
    if os.path.lexists(requested) or root.exists():
        raise FileExistsError(f"fixture runtime root must not exist: {root}")
    return root


def _job_proof(run_dir: Path, finalized: dict[str, Any]) -> dict[str, Any]:
    """Reference evidence already hash-verified by load_finalized_run."""
    artifacts = {
        descriptor["relative_path"]: descriptor
        for descriptor in finalized["artifacts"].values()
    }
    if any(relative not in artifacts for relative in _PROOF_ARTIFACTS):
        raise ValueError(
            "finalized fixture is missing job proof or benchmark artifacts"
        )
    oracle = json.loads(
        (run_dir / "oracle/hadoop-oracle-manifest.json").read_text(encoding="utf-8")
    )
    jobs = oracle.get("jobs") if isinstance(oracle, dict) else None
    job_ids = {}
    for name in ("aggregate", "source_records"):
        job = jobs.get(name) if isinstance(jobs, dict) else None
        identifier = job.get("hadoop_job_id") if isinstance(job, dict) else None
        if not isinstance(identifier, str) or not re.fullmatch(
            r"job_[0-9]+_[0-9]+", identifier
        ):
            raise ValueError(f"fixture Hadoop job proof is missing: {name}")
        job_ids[name] = identifier
    return {
        "hadoop_job_ids": job_ids,
        "artifacts": {relative: artifacts[relative] for relative in _PROOF_ARTIFACTS},
    }


def _numeric_contract_proof(runtime_root: Path) -> dict[str, Any]:
    relative = "_numeric-contract/numeric-contract.json"
    proof_path = runtime_root / relative
    try:
        proof_path.resolve(strict=True).relative_to(runtime_root)
        if proof_path.is_symlink():
            raise ValueError("numeric contract proof must not be a symbolic link")
        payload = proof_path.read_bytes()
        proof = json.loads(payload)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("cannot read numeric contract proof") from exc
    if (
        not isinstance(proof, dict)
        or proof.get("schema_version") != "spark-numeric-contract-check-v1"
        or proof.get("status") != "passed"
    ):
        raise ValueError("numeric contract proof has not passed")
    return {
        "relative_path": relative,
        "sha256": hashlib.sha256(payload).hexdigest(),
        "byte_size": len(payload),
        "status": "passed",
    }


def execute_fixture_acceptance(
    *,
    machine_metadata_path: Path,
    runtime_root: Path | None = None,
    repository: Path,
    python_executable: Path,
    confirmation: str,
) -> dict[str, Any]:
    """Run a fresh fixed fixture matrix, publishing only after both gates pass.

    Relative runtime paths are repository-relative. An explicit runtime root
    overrides PIPELINE_RUNTIME_DIR; otherwise that variable supplies the root.
    The selected absolute root is passed to Compose for its runtime bind mount.
    Existing roots are never resumed, even after an unsuccessful invocation.
    """
    require_execution_confirmation(confirmation)
    # Capture the validated bytes once so each run receives identical metadata.
    try:
        machine_bytes = machine_metadata_path.read_bytes()
        machine = json.loads(machine_bytes)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("cannot read machine metadata") from exc
    if not isinstance(machine, dict):
        raise ValueError("machine metadata must be a JSON object")
    validate_machine_metadata(machine)
    machine_hash = hashlib.sha256(machine_bytes).hexdigest()
    repository = repository.resolve(strict=True)
    runtime_root = _fresh_runtime(repository, runtime_root)
    matrix_path = repository / "configs/experiments.toml"
    matrix = load_experiment_matrix(matrix_path)
    matrix_hash = _sha256(matrix_path)
    # 5M resolves the fixed policy only; no source dataset is read or required.
    runs = [
        run
        for run in build_planned_runs(matrix, 5_000_000)
        if run["event_count"] == "fixture"
    ]
    if len(runs) != 9 or len({run["run_id"] for run in runs}) != 9:
        raise ValueError("fixture policy must contain exactly nine distinct cases")

    environment = dict(os.environ)
    environment["PIPELINE_RUNTIME_DIR"] = str(runtime_root)
    if not environment.get("COMPOSE_PROJECT_NAME"):
        runtime_hash = hashlib.sha256(str(runtime_root).encode("utf-8")).hexdigest()
        environment["COMPOSE_PROJECT_NAME"] = f"iot-energy-fixture-{runtime_hash[:16]}"
    start = CommandSpec(
        "services_start",
        (
            "docker",
            "compose",
            "up",
            "-d",
            "--build",
            "--wait",
            "--wait-timeout",
            "300",
            "kafka",
            "spark",
            "spark-worker",
            "hdfs",
            "hadoop",
        ),
        repository,
    )
    stop = CommandSpec("services_stop", ("docker", "compose", "stop"), repository)
    # Exclusive mkdir rejects a competing invocation before it can own services.
    runtime_root.mkdir(parents=True, exist_ok=False)
    logs = runtime_root / "_orchestration-logs"
    completed = []
    primary_error: BaseException | None = None
    try:
        _LOGGER.info(
            "Stage services_start: project %s", environment["COMPOSE_PROJECT_NAME"]
        )
        _run_command(
            start, environment=environment, log_dir=logs / "services", sequence=1
        )
        _LOGGER.info("Stage numeric_contract: checking Spark numeric round trips")
        _run_command(
            CommandSpec(
                "numeric_contract",
                (
                    "docker",
                    "compose",
                    "run",
                    "--rm",
                    "spark-client",
                    "/opt/spark/bin/spark-submit",
                    "--master",
                    "spark://spark:7077",
                    "--conf",
                    "spark.sql.shuffle.partitions=4",
                    "/opt/pipeline/jobs/spark/check_numeric_contract.py",
                    "--output-root",
                    "/workspace/runtime/_numeric-contract",
                ),
                repository,
            ),
            environment=environment,
            log_dir=logs / "validation",
            sequence=1,
        )
        numeric_contract = _numeric_contract_proof(runtime_root)
        for number, run in enumerate(runs, start=1):
            _LOGGER.info("Run %d/%d: %s preparing", number, len(runs), run["run_id"])
            run_dir = runtime_root / run["run_id"]
            plan = _prepare_run(run, run_dir / "snapshot", run_dir)
            with (run_dir / "machine-metadata.json").open("xb") as stream:
                stream.write(machine_bytes)
            commands = build_processing_commands(
                repository=repository,
                runtime_root=runtime_root,
                run_dir=run_dir,
                plan=plan,
                python_executable=python_executable,
                interrupted_recovery=(run.get("mode") == "interrupted_resumed"),
            )
            for sequence, command in enumerate(commands, start=1):
                _LOGGER.info(
                    "Run %d/%d %s: stage %d/%d %s",
                    number,
                    len(runs),
                    run["run_id"],
                    sequence,
                    len(commands),
                    command.stage,
                )
                _run_command(
                    command,
                    environment=environment,
                    log_dir=logs / f"{number:02d}-{run['run_id']}",
                    sequence=sequence,
                )
            _LOGGER.info("Run %s: validating sealed artifacts", run["run_id"])
            finalized = load_finalized_run(run_dir)
            if finalized.get("replay_run_id") != run["run_id"]:
                raise ValueError("finalized fixture run identity mismatch")
            completed.append(
                {
                    "run_id": run["run_id"],
                    "experiment": run["experiment"],
                    "event_count": run["event_count"],
                    "repetition": run["repetition"],
                    "status": "finalized",
                    "run_manifest": f"{run['run_id']}/run-manifest.json",
                    "run_manifest_sha256": _sha256(run_dir / "run-manifest.json"),
                    "artifact_count": len(finalized["artifacts"]),
                    "job_proof": _job_proof(run_dir, finalized),
                }
            )
        _LOGGER.info("Checking cross-run acceptance")
        cross_run = evaluate_cross_run_acceptance(runtime_root)
        _LOGGER.info("Checking recovery equivalence")
        recovery = _recovery_equivalence(runtime_root)
    except BaseException as exc:
        primary_error = exc
        raise
    finally:
        try:
            _LOGGER.info(
                "Stage services_stop: project %s", environment["COMPOSE_PROJECT_NAME"]
            )
            _run_command(
                stop, environment=environment, log_dir=logs / "services", sequence=2
            )
        except BaseException as cleanup_error:
            # Persist diagnostics outside sealed runs and preserve the first error.
            try:
                _write_new(
                    runtime_root / "cleanup-diagnostic.json",
                    {
                        "schema_version": "fixture-cleanup-diagnostic-v1",
                        "status": "failed",
                        "compose_project_name": environment["COMPOSE_PROJECT_NAME"],
                        "cleanup_error": repr(cleanup_error),
                        "primary_error": repr(primary_error) if primary_error else None,
                    },
                )
            except BaseException as diagnostic_error:
                cleanup_error.add_note(
                    f"Cannot record cleanup diagnostic: {diagnostic_error}"
                )
            if primary_error is None:
                raise
            primary_error.add_note(f"Service cleanup also failed: {cleanup_error}")
            for note in getattr(cleanup_error, "__notes__", ()):
                primary_error.add_note(note)

    result = {
        "schema_version": "fixture-acceptance-v1",
        "status": "complete",
        "matrix_sha256": matrix_hash,
        "machine_metadata_sha256": machine_hash,
        "numeric_contract": numeric_contract,
        "compose_project_name": environment["COMPOSE_PROJECT_NAME"],
        "runs": completed,
        "correctness_semantic_equivalence": cross_run[
            "correctness_semantic_equivalence"
        ],
        "watermark_effect": cross_run["watermark_effect"],
        "recovery_semantic_equivalence": recovery,
    }
    _write_new(runtime_root / "fixture-acceptance.json", result)
    _LOGGER.info(
        "Fixture acceptance complete: %s", runtime_root / "fixture-acceptance.json"
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--machine-metadata", type=Path, required=True)
    parser.add_argument(
        "--runtime-root",
        type=Path,
        help="fresh directory below reports/runtime (default: PIPELINE_RUNTIME_DIR)",
    )
    parser.add_argument("--repository", type=Path, default=Path.cwd())
    parser.add_argument("--python", type=Path, default=Path(sys.executable))
    parser.add_argument(
        "--confirm", required=True, help=f"required literal: {EXECUTION_CONFIRMATION}"
    )
    args = parser.parse_args()
    # StreamHandler flushes each progress record; stdout remains the final JSON.
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        stream=sys.stderr,
    )
    result = execute_fixture_acceptance(
        machine_metadata_path=args.machine_metadata,
        runtime_root=args.runtime_root,
        repository=args.repository,
        python_executable=args.python,
        confirmation=args.confirm,
    )
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
