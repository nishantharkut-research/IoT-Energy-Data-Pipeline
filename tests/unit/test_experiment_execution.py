from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pytest

from iot_energy_pipeline import experiment_execution as execution
from iot_energy_pipeline.experiment_execution import (
    EXECUTION_CONFIRMATION,
    _safe_run_id,
    _validate_execution_plan,
    build_processing_commands,
    evaluate_cross_run_acceptance,
    execute_experiment_plan,
    require_execution_confirmation,
)
from iot_energy_pipeline.experiment_plan import build_planned_runs
from iot_energy_pipeline.reports import load_experiment_matrix


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


@pytest.mark.parametrize("seconds", [True, -1, float("nan"), float("inf")])
def test_workflow_receipt_refuses_invalid_measurements(tmp_path: Path, seconds) -> None:
    receipt = {
        "schema_version": "workflow-receipt-v1",
        "run_id": "run",
        "timing_scope": execution.WORKFLOW_TIMING_SCOPE,
        "workflow_seconds": seconds,
        "bindings": {"plan": "a" * 64},
    }
    _write(tmp_path / "workflow-receipt.json", json.dumps(receipt))
    with pytest.raises(ValueError, match="workflow receipt"):
        execution.load_workflow_receipt(
            tmp_path, run_id="run", bindings=receipt["bindings"]
        )


def test_workflow_receipt_is_bound_to_executed_plan(tmp_path: Path) -> None:
    receipt = {
        "schema_version": "workflow-receipt-v1",
        "run_id": "run",
        "timing_scope": execution.WORKFLOW_TIMING_SCOPE,
        "workflow_seconds": 1.25,
        "bindings": {"plan": "a" * 64},
    }
    _write(tmp_path / "workflow-receipt.json", json.dumps(receipt))
    assert (
        execution.load_workflow_receipt(
            tmp_path, run_id="run", bindings=receipt["bindings"]
        )
        == receipt
    )
    with pytest.raises(ValueError, match="bindings"):
        execution.load_workflow_receipt(
            tmp_path, run_id="run", bindings={"plan": "b" * 64}
        )


def _plan() -> dict:
    return {
        "run_id": "scale-100000-r01",
        "topic": "iot-energy-scale-100000-r01",
        "replay_manifest_hash": "a" * 64,
        "canonical_ndjson_sha256": "b" * 64,
        "watermark": "24 hours",
        "max_offsets_per_trigger": 10000,
    }


def _fixed_execution_plan(full_event_count: int = 3_250_000) -> dict:
    matrix_path = Path("configs/experiments.toml")
    matrix = load_experiment_matrix(matrix_path)
    return {
        "schema_version": "experiment-plan-v1",
        "status": "planned_not_executed",
        "execution_gate": "explicit execute command required",
        "matrix_sha256": hashlib.sha256(matrix_path.read_bytes()).hexdigest(),
        "snapshot_manifest_sha256": "a" * 64,
        "canonical_ndjson_sha256": "b" * 64,
        "machine_metadata_sha256": "c" * 64,
        "full_event_count": full_event_count,
        "summary_statistics": ["median", "minimum", "maximum"],
        "storage_formats": matrix["storage"]["formats"],
        "query_names": matrix["queries"]["names"],
        "normalized_tariff_rates": matrix["business"]["normalized_rates"],
        "monetary_interpretation": "hypothetical scenarios; not HKUST results",
        "runs": build_planned_runs(matrix, full_event_count),
    }


def test_execution_requires_exact_designated_machine_confirmation() -> None:
    with pytest.raises(ValueError, match="confirmation"):
        require_execution_confirmation("yes")

    require_execution_confirmation(EXECUTION_CONFIRMATION)

    with pytest.raises(ValueError, match="confirmation"):
        execute_experiment_plan(
            experiment_plan_path=Path("missing-plan.json"),
            snapshot_dir=Path("missing-snapshot"),
            machine_metadata_path=Path("missing-machine.json"),
            runtime_root=Path("missing-runtime"),
            repository=Path.cwd(),
            python_executable=Path("python"),
            confirmation="no",
        )


@pytest.mark.parametrize(
    "run_id",
    ("../escape", "nested/run", "nested\\run", ".", "a" * 129),
)
def test_execution_rejects_unsafe_run_ids_before_preparation(run_id: str) -> None:
    with pytest.raises(ValueError, match="run_id"):
        _safe_run_id(run_id)

    assert _safe_run_id("correctness-clean-r01") == "correctness-clean-r01"


def test_execution_rederives_and_validates_the_fixed_compiled_plan() -> None:
    plan = _fixed_execution_plan()

    assert (
        _validate_execution_plan(
            plan, repository=Path.cwd(), full_event_count=3_250_000
        )
        == plan["runs"]
    )

    changed = {**plan, "runs": [dict(run) for run in plan["runs"]]}
    changed["runs"][0]["fault"] = "delayed"
    with pytest.raises(ValueError, match="run matrix"):
        _validate_execution_plan(
            changed, repository=Path.cwd(), full_event_count=3_250_000
        )

    with pytest.raises(ValueError, match="compiled policy"):
        _validate_execution_plan(
            {**plan, "matrix_sha256": "0" * 64},
            repository=Path.cwd(),
            full_event_count=3_250_000,
        )


def test_processing_commands_cover_every_fail_closed_stage(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    runtime = repository / "reports/runtime"
    run = runtime / "scale-100000-r01"
    commands = build_processing_commands(
        repository=repository,
        runtime_root=runtime,
        run_dir=run,
        plan=_plan(),
        python_executable=Path("python"),
        interrupted_recovery=False,
    )

    assert [command.stage for command in commands] == [
        "replay",
        "spark_stream",
        "spark_gold",
        "spark_layer_audit",
        "hadoop_oracle",
        "reconciliation",
        "decision_impact",
        "storage_benchmark",
        "query_benchmark",
        "run_seal",
    ]
    rendered = [" ".join(str(part) for part in command.argv) for command in commands]
    assert all("F:\\" not in command for command in rendered)
    assert (
        sum("/workspace/runtime/scale-100000-r01" in command for command in rendered)
        >= 5
    )
    assert "available" not in rendered[0]
    assert commands[0].argv[-1] == "127.0.0.1:29092"
    assert "iot_energy_pipeline.run_finalization" in rendered[-1]
    decision = next(
        command for command in commands if command.stage == "decision_impact"
    )
    assert decision.argv.count("--oracle-dir") == 1
    spark_commands = [
        command for command in commands if "/opt/spark/bin/spark-submit" in command.argv
    ]
    assert len(spark_commands) == 5
    for command in spark_commands:
        index = command.argv.index("--conf")
        assert command.argv[index + 1] == "spark.sql.shuffle.partitions=4"
        assert index < next(
            i for i, argument in enumerate(command.argv) if argument.endswith(".py")
        )


def test_run_command_records_exact_arguments(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    command = execution.CommandSpec(
        "spark_stream",
        ("spark-submit", "--conf", "spark.sql.shuffle.partitions=4", "stream.py"),
        tmp_path,
    )
    monkeypatch.setattr(
        execution.subprocess,
        "run",
        lambda argv, **kwargs: execution.subprocess.CompletedProcess(argv, 0),
    )
    execution._run_command(command, environment={}, log_dir=tmp_path, sequence=1)
    recorded = json.loads((tmp_path / "01-spark_stream.command.json").read_text())
    assert recorded == {
        "stage": command.stage,
        "argv": list(command.argv),
        "cwd": str(tmp_path),
    }


def test_interrupted_recovery_has_interrupt_then_resume_replay(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    runtime = repository / "reports/runtime"
    commands = build_processing_commands(
        repository=repository,
        runtime_root=runtime,
        run_dir=runtime / "recovery-interrupted_resumed-r01",
        plan={**_plan(), "run_id": "recovery-interrupted_resumed-r01"},
        python_executable=Path("python"),
        interrupted_recovery=True,
    )

    assert [command.stage for command in commands[:2]] == [
        "replay_interrupt",
        "replay_resume",
    ]
    assert "--interrupt-after" in commands[0].argv
    assert "--resume" in commands[1].argv


def test_cross_run_acceptance_requires_fault_equivalence_and_watermark_effect(
    tmp_path: Path,
) -> None:
    payloads = {
        "gold/gold-source-events.ndjson": '{"source":1}\n',
        "gold/gold-aggregates.ndjson": '{"aggregate":1}\n',
        "oracle/hadoop-source-records.ndjson": '{"source":1}\n',
        "oracle/hadoop-aggregates.ndjson": '{"aggregate":1}\n',
    }
    for fault in ("clean", "duplicate", "delayed", "malformed", "combined"):
        root = tmp_path / f"correctness-{fault}-r01"
        for relative, content in payloads.items():
            _write(root / relative, content)
    for mode, affected in (("retaining", 0), ("restrictive", 2)):
        root = tmp_path / f"watermark-{mode}-r01"
        for relative, content in payloads.items():
            _write(root / relative, content)
        _write(
            root / "reports/decision-impact.json",
            json.dumps(
                {
                    "affected_meter_period_count": affected,
                    "absolute_kwh_discrepancy": str(affected),
                }
            ),
        )

    result = evaluate_cross_run_acceptance(tmp_path)

    assert result["correctness_semantic_equivalence"]["status"] == "identical"
    assert result["watermark_effect"]["gold_status"] == "identical"
    assert result["watermark_effect"]["candidate_difference_exposed"] is True


def test_prepare_run_passes_compiled_repetition(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured = {}

    def prepare(**kwargs):
        captured.update(kwargs)
        return {"status": "prepared"}

    monkeypatch.setattr(execution, "prepare_distributed_run", prepare)
    run = next(
        run
        for run in _fixed_execution_plan()["runs"]
        if run["experiment"] == "scale" and run["repetition"] == 3
    )
    execution._prepare_run(run, tmp_path / "snapshot", tmp_path / run["run_id"])
    assert captured["repetition"] == 3


@pytest.fixture
def executor_harness(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    repository = tmp_path / "repository"
    repository.mkdir()
    matrix = repository / "configs/experiments.toml"
    matrix.parent.mkdir()
    shutil.copyfile("configs/experiments.toml", matrix)
    snapshot = repository / "snapshot"
    canonical = snapshot / "canonical.ndjson"
    _write(canonical, "{}\n")
    snapshot_manifest = snapshot / "snapshot-manifest.json"
    _write(
        snapshot_manifest,
        json.dumps(
            {
                "artifacts": {
                    "canonical_ndjson": {
                        "file": "canonical.ndjson",
                        "record_count": 1_000_000,
                        "sha256": hashlib.sha256(canonical.read_bytes()).hexdigest(),
                    }
                }
            }
        ),
    )
    machine = repository / "machine.json"
    _write(
        machine,
        json.dumps(
            {
                "schema_version": "machine-metadata-v1",
                "captured_at_utc": "2026-10-27T00:00:00Z",
                "execution_context": "designated_machine",
                "hostname": "test-host",
                "operating_system": "test-os",
                "processor": "test-cpu",
                "logical_cpu_count": 2,
                "memory_bytes": 1024,
                "software": dict.fromkeys(
                    ("python", "docker", "kafka", "spark", "hadoop"), "test-version"
                ),
            }
        ),
    )
    plan = _fixed_execution_plan(1_000_000)
    plan.update(
        {
            "canonical_ndjson_sha256": hashlib.sha256(
                canonical.read_bytes()
            ).hexdigest(),
            "snapshot_manifest_sha256": hashlib.sha256(
                snapshot_manifest.read_bytes()
            ).hexdigest(),
            "machine_metadata_sha256": hashlib.sha256(machine.read_bytes()).hexdigest(),
        }
    )
    plan_path = repository / "plan.json"
    _write(plan_path, json.dumps(plan))
    events = []
    commands = []

    def prepare(run, snapshot_dir, run_dir):
        events.append(("prepare", run["experiment"]))
        if run["experiment"] == "scale":
            raise RuntimeError("scale reached")
        _write(run_dir / "run-manifest.json", "{}")
        return {**_plan(), "run_id": run["run_id"]}

    def run_command(command, **kwargs):
        commands.append(command)

    def load_run(run_dir):
        events.append(("sealed", run_dir.name))
        return {"artifacts": []}

    monkeypatch.setattr(execution, "_prepare_run", prepare)
    monkeypatch.setattr(execution, "_run_command", run_command)
    monkeypatch.setattr(execution, "load_finalized_run", load_run)
    return (
        {
            "experiment_plan_path": plan_path,
            "snapshot_dir": snapshot,
            "machine_metadata_path": machine,
            "runtime_root": repository / "runtime",
            "repository": repository,
            "python_executable": Path("python"),
            "confirmation": EXECUTION_CONFIRMATION,
        },
        events,
        commands,
    )


@pytest.mark.parametrize("failure", [None, "cross_run", "recovery"])
def test_executor_gates_scale_after_all_fixtures(
    executor_harness, monkeypatch: pytest.MonkeyPatch, failure: str | None
) -> None:
    arguments, events, commands = executor_harness

    def cross_run(root):
        events.append(("gate", "cross_run"))
        if failure == "cross_run":
            raise ValueError("cross_run rejected")
        return {}

    def recovery(root):
        events.append(("gate", "recovery"))
        if failure == "recovery":
            raise ValueError("recovery rejected")
        return {}

    monkeypatch.setattr(execution, "evaluate_cross_run_acceptance", cross_run)
    monkeypatch.setattr(execution, "_recovery_equivalence", recovery)
    error = ValueError if failure else RuntimeError
    message = f"{failure} rejected" if failure else "scale reached"
    with pytest.raises(error, match=message):
        execute_experiment_plan(**arguments)
    gate_index = events.index(("gate", "cross_run"))
    assert sum(event[0] == "sealed" for event in events[:gate_index]) == 9
    expected = [("gate", "cross_run")]
    if failure != "cross_run":
        expected.append(("gate", "recovery"))
    if failure is None:
        expected.append(("prepare", "scale"))
    assert events[gate_index:] == expected
    assert commands[-1].stage == "services_stop"
    assert not (arguments["runtime_root"] / "experiment-results.json").exists()


def test_executor_waits_for_healthy_services(executor_harness) -> None:
    arguments, events, commands = executor_harness
    with pytest.raises((RuntimeError, FileNotFoundError)):
        execute_experiment_plan(**arguments)
    assert commands[0].stage == "services_start"
    argv = commands[0].argv
    assert "--wait" in argv
    assert argv[argv.index("--wait-timeout") + 1] == "300"


def test_executor_checks_canonical_bytes_in_one_pass(executor_harness, monkeypatch):
    import iot_energy_pipeline.experiment_plan as module

    arguments, _, _ = executor_harness
    original = module._sha256
    reads = []

    def counted(path):
        if path.name == "canonical.ndjson":
            reads.append(path)
        return original(path)

    monkeypatch.setattr(module, "_sha256", counted)
    monkeypatch.setattr(execution, "_sha256", counted)

    def stop(command, **kwargs):
        if command.stage == "services_start":
            raise RuntimeError("validation completed")

    monkeypatch.setattr(execution, "_run_command", stop)
    with pytest.raises(RuntimeError, match="validation completed"):
        execute_experiment_plan(**arguments)
    assert len(reads) == 1


def test_executor_rejects_plan_hash_disagreement(executor_harness):
    arguments, _, commands = executor_harness
    path = arguments["experiment_plan_path"]
    plan = json.loads(path.read_text())
    plan["canonical_ndjson_sha256"] = "0" * 64
    path.write_text(json.dumps(plan))
    with pytest.raises(ValueError, match="canonical snapshot binding"):
        execute_experiment_plan(**arguments)
    assert not commands


@pytest.mark.parametrize("stage", ["services_start", "services_stop"])
def test_service_command_logs_only_project_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, stage: str
) -> None:
    environment = {
        "COMPOSE_PROJECT_NAME": "explicit-project",
        "PIPELINE_RUNTIME_DIR": str(tmp_path),
        "AWS_SECRET_ACCESS_KEY": "never-log-this",
    }
    captured = {}

    def run(argv, **kwargs):
        captured.update(kwargs["env"])
        return execution.subprocess.CompletedProcess(argv, 0)

    monkeypatch.setattr(execution.subprocess, "run", run)
    command = execution.CommandSpec(stage, ("docker", "compose", "stop"), tmp_path)
    execution._run_command(
        command, environment=environment, log_dir=tmp_path, sequence=1
    )
    log_path = tmp_path / f"01-{stage}.command.json"
    recorded = json.loads(log_path.read_text())
    assert recorded["environment"] == {"COMPOSE_PROJECT_NAME": "explicit-project"}
    assert "never-log-this" not in log_path.read_text()
    assert captured == environment


@pytest.mark.parametrize("explicit_project", [None, "user-chosen-project"])
def test_executor_isolates_resolved_roots_and_honors_explicit_project(
    executor_harness, monkeypatch: pytest.MonkeyPatch, explicit_project: str | None
) -> None:
    arguments, _, _ = executor_harness
    monkeypatch.delenv("COMPOSE_PROJECT_NAME", raising=False)
    if explicit_project is not None:
        monkeypatch.setenv("COMPOSE_PROJECT_NAME", explicit_project)
    calls = []

    def run(command, *, environment, **kwargs):
        calls.append((command.stage, dict(environment)))
        if command.stage == "services_start":
            raise RuntimeError("startup failed")

    monkeypatch.setattr(execution, "_run_command", run)
    root = arguments["runtime_root"]
    roots = [root, root / ".." / root.name, root.with_name("fresh-attempt")]
    for runtime_root in roots:
        with pytest.raises(RuntimeError, match="startup failed"):
            execute_experiment_plan(**{**arguments, "runtime_root": runtime_root})
    starts = [env for stage, env in calls if stage == "services_start"]
    projects = [env["COMPOSE_PROJECT_NAME"] for env in starts]
    if explicit_project is not None:
        assert projects == [explicit_project] * 3
    else:
        assert projects[0] == projects[1]
        assert projects[0] != projects[2]
        for project, runtime_root in zip(projects, roots, strict=True):
            digest = hashlib.sha256(str(runtime_root.resolve()).encode()).hexdigest()
            assert digest[:16] in project
            assert project.startswith("iot-energy-")
    assert execution.os.environ.get("COMPOSE_PROJECT_NAME") == explicit_project
    assert [stage for stage, _ in calls] == ["services_start", "services_stop"] * 3
    stops = [env for stage, env in calls if stage == "services_stop"]
    assert [env["COMPOSE_PROJECT_NAME"] for env in stops] == projects


@pytest.mark.parametrize("stage", ["services_start", "spark_stream"])
@pytest.mark.parametrize("cleanup_fails", [False, True])
def test_executor_cleans_up_partial_start_and_preserves_original_error(
    executor_harness, monkeypatch: pytest.MonkeyPatch, stage: str, cleanup_fails: bool
) -> None:
    arguments, _, _ = executor_harness
    monkeypatch.delenv("COMPOSE_PROJECT_NAME", raising=False)
    original = RuntimeError("original stage failure")
    calls = []

    def run(command, *, environment, **kwargs):
        calls.append((command, dict(environment)))
        if command.stage == stage:
            raise original
        if command.stage == "services_stop" and cleanup_fails:
            raise RuntimeError("cleanup failed")

    monkeypatch.setattr(execution, "_run_command", run)
    with pytest.raises(RuntimeError) as caught:
        execute_experiment_plan(**arguments)
    assert caught.value is original
    assert calls[-1][0].stage == "services_stop"
    assert calls[-1][0].argv == ("docker", "compose", "stop")
    assert calls[0][1]["COMPOSE_PROJECT_NAME"] == calls[-1][1]["COMPOSE_PROJECT_NAME"]
    assert not (arguments["runtime_root"] / "experiment-results.json").exists()
    if cleanup_fails:
        assert any("cleanup failed" in note for note in original.__notes__)


def test_executor_propagates_cleanup_failure_after_successful_processing(
    executor_harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    arguments, _, _ = executor_harness
    cleanup_error = RuntimeError("cleanup failed after processing")

    def prepare(run, snapshot_dir, run_dir):
        _write(run_dir / "run-manifest.json", "{}")
        return {**_plan(), "run_id": run["run_id"]}

    def run(command, **kwargs):
        if command.stage == "services_stop":
            raise cleanup_error

    monkeypatch.setattr(execution, "_prepare_run", prepare)
    monkeypatch.setattr(execution, "_run_command", run)
    monkeypatch.setattr(execution, "evaluate_cross_run_acceptance", lambda root: {})
    monkeypatch.setattr(execution, "_recovery_equivalence", lambda root: {})
    with pytest.raises(RuntimeError) as caught:
        execute_experiment_plan(**arguments)
    assert caught.value is cleanup_error
    assert not (arguments["runtime_root"] / "experiment-results.json").exists()
