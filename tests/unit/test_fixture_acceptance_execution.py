"""Orchestration tests only: subprocesses are mocked; no jobs are executed."""

from __future__ import annotations

import hashlib
import importlib
import importlib.util
import json
import logging
import shutil
import sys
from pathlib import Path

import pytest

from dashboard.data import REQUIRED_VIEWS
from iot_energy_pipeline.experiment_execution import EXECUTION_CONFIRMATION
from iot_energy_pipeline.experiment_plan import build_planned_runs
from iot_energy_pipeline.reports import load_experiment_matrix


def test_public_fixture_acceptance_module_exists() -> None:
    assert (
        importlib.util.find_spec("iot_energy_pipeline.fixture_acceptance") is not None
    )


def _json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _mock_numeric_contract() -> dict:
    """Match the job's proof format without claiming Spark executed in unit tests."""
    bound = 10**38 - 1
    return {
        "schema_version": "spark-numeric-contract-check-v1",
        "status": "passed",
        "spark_version": "mock-version",
        "storage_type": "decimal(38,0)",
        "python_decimal_precision": 6,
        "json_parse_parquet_and_json_export": [
            {"case": "negative-boundary", "exact_scaled_integer": str(-bound)},
            {"case": "positive-boundary", "exact_scaled_integer": str(bound)},
            {"case": "source-witness", "exact_scaled_integer": "26724700000000000000"},
        ],
        "overflow_guard_cases": [str(-(10**38)), str(10**38)],
        "scope": "three synthetic numeric cases; not a scale measurement",
    }


def _seal_mock_outputs(run_dir: Path) -> None:
    """Test doubles for job outputs, never evidence of distributed execution."""
    _json(run_dir / "gold/gold-manifest.json", {"status": "gold_finalized"})
    _json(
        run_dir / "oracle/hadoop-oracle-manifest.json",
        {
            "jobs": {
                "aggregate": {"hadoop_job_id": "job_123_0001"},
                "source_records": {"hadoop_job_id": "job_123_0002"},
            }
        },
    )
    for relative in (
        "layer-audit/layer-audit-manifest.json",
        "reports/reconciliation.json",
        "storage/storage-benchmark.json",
        "reports/query-benchmark.json",
    ):
        _json(run_dir / relative, {"test_double": True})
    _json(
        run_dir / "reports/decision-impact.json",
        {"affected_meter_period_count": 2 if "restrictive" in run_dir.name else 1},
    )
    for relative in (
        "gold/gold-source-events.ndjson",
        "gold/gold-aggregates.ndjson",
        "oracle/hadoop-source-records.ndjson",
        "oracle/hadoop-aggregates.ndjson",
    ):
        (run_dir / relative).write_text('{"test_double":true}\n', encoding="utf-8")
    artifacts = {}
    for path in run_dir.rglob("*"):
        if path.is_file():
            relative = path.relative_to(run_dir).as_posix()
            artifacts[relative.replace("/", "__")] = {
                "relative_path": relative,
                "byte_size": path.stat().st_size,
                "sha256": _digest(path),
            }
    _json(
        run_dir / "run-manifest.json",
        {
            "schema_version": "finalized-run-v1",
            "status": "finalized",
            "reconciled": True,
            "immutable": True,
            "replay_run_id": run_dir.name,
            "artifacts": artifacts,
            "views": dict.fromkeys(REQUIRED_VIEWS, {}),
        },
    )
    (run_dir / "run-manifest.sha256").write_text(
        _digest(run_dir / "run-manifest.json"), encoding="ascii"
    )


@pytest.fixture
def harness(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    acceptance = importlib.import_module("iot_energy_pipeline.fixture_acceptance")
    repository = tmp_path / "repository"
    matrix_path = repository / "configs/experiments.toml"
    matrix_path.parent.mkdir(parents=True)
    shutil.copyfile("configs/experiments.toml", matrix_path)
    machine = repository / "machine.json"
    _json(
        machine,
        {
            "schema_version": "machine-metadata-v1",
            "captured_at_utc": "2026-10-27T00:00:00Z",
            "execution_context": "designated_machine",
            "hostname": "mock-host",
            "operating_system": "mock-os",
            "processor": "mock-cpu",
            "logical_cpu_count": 2,
            "memory_bytes": 1024,
            "software": dict.fromkeys(
                ("python", "docker", "kafka", "spark", "hadoop"), "mock-version"
            ),
        },
    )
    root = repository / "reports/runtime/fresh-fixtures"
    events = []
    commands = []
    environments = []
    prepared = []

    def prepare(run, snapshot_dir, run_dir):
        assert run["event_count"] == "fixture"
        assert not snapshot_dir.exists()  # No source snapshot dependency.
        assert not run_dir.exists()
        events.append(("prepare", run["run_id"]))
        prepared.append(run)
        plan = {
            "run_id": run["run_id"],
            "topic": "mock-" + run["run_id"],
            "replay_manifest_hash": "a" * 64,
            "canonical_ndjson_sha256": "b" * 64,
            "watermark": run["watermark"],
            "max_offsets_per_trigger": run["max_offsets_per_trigger"],
        }
        _json(run_dir / "distributed-plan.json", plan)
        return plan

    def command(command, *, environment, log_dir, sequence):
        commands.append(command)
        environments.append(dict(environment))
        events.append(("command", command.stage))
        if command.stage == "numeric_contract":
            selected_root = Path(environment["PIPELINE_RUNTIME_DIR"])
            assert log_dir == selected_root / "_orchestration-logs/validation"
            assert sequence == 1
            _json(
                selected_root / "_numeric-contract/numeric-contract.json",
                _mock_numeric_contract(),
            )
        if command.stage == "run_seal":
            run_dir = Path(command.argv[command.argv.index("--run-dir") + 1])
            assert (
                run_dir / "machine-metadata.json"
            ).read_bytes() == machine.read_bytes()
            _seal_mock_outputs(run_dir)

    real_load = acceptance.load_finalized_run
    real_cross = acceptance.evaluate_cross_run_acceptance
    real_recovery = acceptance._recovery_equivalence

    def load(run_dir):
        events.append(("loaded", run_dir.name))
        return real_load(run_dir)

    def cross(runtime_root):
        events.append(("gate", "cross_run"))
        return real_cross(runtime_root)

    def recovery(runtime_root):
        events.append(("gate", "recovery"))
        return real_recovery(runtime_root)

    monkeypatch.setattr(acceptance, "_prepare_run", prepare)
    monkeypatch.setattr(acceptance, "_run_command", command)
    monkeypatch.setattr(acceptance, "load_finalized_run", load)
    monkeypatch.setattr(acceptance, "evaluate_cross_run_acceptance", cross)
    monkeypatch.setattr(acceptance, "_recovery_equivalence", recovery)
    monkeypatch.delenv("COMPOSE_PROJECT_NAME", raising=False)
    monkeypatch.delenv("PIPELINE_RUNTIME_DIR", raising=False)
    return {
        "module": acceptance,
        "arguments": {
            "repository": repository,
            "runtime_root": root,
            "machine_metadata_path": machine,
            "python_executable": Path(sys.executable),
            "confirmation": EXECUTION_CONFIRMATION,
        },
        "events": events,
        "commands": commands,
        "environments": environments,
        "prepared": prepared,
        "command": command,
    }


def test_runs_exact_fixture_matrix_all_stages_seals_then_gates(harness) -> None:
    arguments = harness["arguments"]
    result = harness["module"].execute_fixture_acceptance(**arguments)
    root = arguments["runtime_root"]
    expected = [
        run
        for run in build_planned_runs(
            load_experiment_matrix(
                arguments["repository"] / "configs/experiments.toml"
            ),
            5_000_000,
        )
        if run["event_count"] == "fixture"
    ]
    assert harness["prepared"] == expected
    assert len(result["runs"]) == 9
    assert result["status"] == "complete"
    assert result["schema_version"] == "fixture-acceptance-v1"
    assert result["machine_metadata_sha256"] == _digest(
        arguments["machine_metadata_path"]
    )
    assert result["matrix_sha256"] == _digest(
        arguments["repository"] / "configs/experiments.toml"
    )
    assert json.loads((root / "fixture-acceptance.json").read_text()) == result
    assert harness["events"][-3:] == [
        ("gate", "cross_run"),
        ("gate", "recovery"),
        ("command", "services_stop"),
    ]
    assert sum(kind == "loaded" for kind, _ in harness["events"]) == 9
    expected_tail = [
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
    stages = [command.stage for command in harness["commands"]]
    assert stages[:2] == ["services_start", "numeric_contract"]
    offset = 2
    for run in expected:
        replay = (
            ["replay_interrupt", "replay_resume"]
            if run.get("mode") == "interrupted_resumed"
            else ["replay"]
        )
        case_stages = replay + expected_tail
        assert stages[offset : offset + len(case_stages)] == case_stages
        offset += len(case_stages)
    assert offset == len(stages) - 1
    start = harness["commands"][0]
    assert start.argv == (
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
    )
    assert harness["commands"][-1].argv == ("docker", "compose", "stop")
    assert harness["commands"][1].argv == (
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
    )
    numeric_path = root / "_numeric-contract/numeric-contract.json"
    assert (
        result["numeric_contract"]["relative_path"]
        == "_numeric-contract/numeric-contract.json"
    )
    assert result["numeric_contract"]["sha256"] == _digest(numeric_path)
    assert harness["events"][1] == ("command", "numeric_contract")
    assert harness["events"][2][0] == "prepare"
    for completed in result["runs"]:
        run_dir = root / completed["run_id"]
        assert completed["run_manifest_sha256"] == _digest(
            run_dir / "run-manifest.json"
        )
        assert completed["job_proof"]["hadoop_job_ids"] == {
            "aggregate": "job_123_0001",
            "source_records": "job_123_0002",
        }
        artifacts = completed["job_proof"]["artifacts"]
        for relative in (
            "gold/gold-manifest.json",
            "oracle/hadoop-oracle-manifest.json",
            "storage/storage-benchmark.json",
            "reports/query-benchmark.json",
        ):
            assert artifacts[relative]["sha256"] == _digest(run_dir / relative)


@pytest.mark.parametrize("confirmation", ["", "yes", EXECUTION_CONFIRMATION + " "])
def test_confirmation_rejected_before_side_effects(harness, confirmation) -> None:
    arguments = {**harness["arguments"], "confirmation": confirmation}
    with pytest.raises(ValueError, match="confirmation"):
        harness["module"].execute_fixture_acceptance(**arguments)
    assert not arguments["runtime_root"].exists()
    assert harness["events"] == []


@pytest.mark.parametrize("metadata", ["missing", "malformed", "invalid"])
def test_metadata_validated_before_creating_root_or_starting_services(
    harness, metadata
) -> None:
    arguments = harness["arguments"]
    machine = arguments["machine_metadata_path"]
    if metadata == "missing":
        machine.unlink()
    elif metadata == "malformed":
        machine.write_text("[", encoding="utf-8")
    else:
        _json(machine, {"schema_version": "machine-metadata-v1"})
    with pytest.raises((ValueError, FileNotFoundError)):
        harness["module"].execute_fixture_acceptance(**arguments)
    assert not arguments["runtime_root"].exists()
    assert harness["events"] == []


@pytest.mark.parametrize("relative", [".", "reports", "reports/runtime", "tmp/other"])
def test_root_must_be_strictly_below_reports_runtime(harness, relative) -> None:
    arguments = harness["arguments"]
    root = arguments["repository"] / relative
    with pytest.raises(ValueError, match="reports/runtime"):
        harness["module"].execute_fixture_acceptance(
            **{**arguments, "runtime_root": root}
        )
    assert harness["events"] == []


@pytest.mark.parametrize("existing", ["empty", "old-run", "file"])
def test_existing_root_is_never_reused_or_overwritten(harness, existing) -> None:
    arguments = harness["arguments"]
    root = arguments["runtime_root"]
    root.parent.mkdir(parents=True)
    if existing == "file":
        root.write_text("keep", encoding="utf-8")
    else:
        root.mkdir()
        if existing == "old-run":
            _json(root / "fixture-acceptance.json", {"keep": True})
    before = sorted((p.name, p.read_bytes()) for p in root.rglob("*") if p.is_file())
    with pytest.raises(FileExistsError):
        harness["module"].execute_fixture_acceptance(**arguments)
    assert harness["events"] == []
    if existing == "file":
        assert root.read_text() == "keep"
    else:
        assert (
            sorted((p.name, p.read_bytes()) for p in root.rglob("*") if p.is_file())
            == before
        )


def test_resolved_path_cannot_escape_runtime_through_a_link(harness, tmp_path) -> None:
    arguments = harness["arguments"]
    parent = arguments["runtime_root"].parent
    parent.mkdir(parents=True)
    outside = tmp_path / "outside"
    outside.mkdir()
    link = parent / "escape"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("symlink creation requires platform privileges")
    with pytest.raises(ValueError, match="reports/runtime"):
        harness["module"].execute_fixture_acceptance(
            **{**arguments, "runtime_root": link / "fresh"}
        )
    assert harness["events"] == []
    assert list(outside.iterdir()) == []


@pytest.mark.parametrize(
    "gate", ["evaluate_cross_run_acceptance", "_recovery_equivalence"]
)
def test_failed_cross_run_gate_prevents_complete_result(
    harness, monkeypatch, gate
) -> None:
    def reject(root):
        assert not (root / "fixture-acceptance.json").exists()
        raise ValueError("acceptance rejected")

    monkeypatch.setattr(harness["module"], gate, reject)
    with pytest.raises(ValueError, match="acceptance rejected"):
        harness["module"].execute_fixture_acceptance(**harness["arguments"])
    assert sum(kind == "loaded" for kind, _ in harness["events"]) == 9
    assert harness["commands"][-1].stage == "services_stop"
    assert not (
        harness["arguments"]["runtime_root"] / "fixture-acceptance.json"
    ).exists()


@pytest.mark.parametrize(
    "stage", ["services_start", "numeric_contract", "spark_stream", "run_seal"]
)
@pytest.mark.parametrize("cleanup_fails", [False, True])
def test_partial_start_or_processing_failure_always_stops_and_preserves_primary(
    harness, monkeypatch, stage, cleanup_fails
) -> None:
    original = RuntimeError("primary failure")
    calls = []

    def command(command, **kwargs):
        calls.append(command.stage)
        if command.stage == stage:
            raise original
        if command.stage == "services_stop" and cleanup_fails:
            raise RuntimeError("cleanup failure")
        harness["command"](command, **kwargs)

    monkeypatch.setattr(harness["module"], "_run_command", command)
    with pytest.raises(RuntimeError) as caught:
        harness["module"].execute_fixture_acceptance(**harness["arguments"])
    assert caught.value is original
    assert calls[-1] == "services_stop"
    root = harness["arguments"]["runtime_root"]
    assert not (root / "fixture-acceptance.json").exists()
    if cleanup_fails:
        diagnostic = json.loads((root / "cleanup-diagnostic.json").read_text())
        assert "cleanup failure" in diagnostic["cleanup_error"]
        assert any("cleanup failure" in note for note in caught.value.__notes__)


def test_cleanup_failure_after_success_prevents_complete_result(
    harness, monkeypatch
) -> None:
    def command(command, **kwargs):
        harness["command"](command, **kwargs)
        if command.stage == "services_stop":
            raise RuntimeError("cleanup failure")

    monkeypatch.setattr(harness["module"], "_run_command", command)
    with pytest.raises(RuntimeError, match="cleanup failure"):
        harness["module"].execute_fixture_acceptance(**harness["arguments"])
    root = harness["arguments"]["runtime_root"]
    assert (root / "cleanup-diagnostic.json").is_file()
    assert not (root / "fixture-acceptance.json").exists()


@pytest.mark.parametrize("explicit_project", [None, "caller-owned-name"])
def test_project_is_scoped_to_root_and_mount_is_the_selected_runtime(
    harness, monkeypatch, explicit_project
) -> None:
    arguments = harness["arguments"]
    if explicit_project:
        monkeypatch.setenv("COMPOSE_PROJECT_NAME", explicit_project)
    monkeypatch.setenv("PIPELINE_RUNTIME_DIR", "stale-mount")
    harness["module"].execute_fixture_acceptance(**arguments)
    environments = harness["environments"]
    expected_project = explicit_project or (
        "iot-energy-fixture-"
        + hashlib.sha256(
            str(arguments["runtime_root"].resolve()).encode("utf-8")
        ).hexdigest()[:16]
    )
    assert all(env["COMPOSE_PROJECT_NAME"] == expected_project for env in environments)
    assert all(
        env["PIPELINE_RUNTIME_DIR"] == str(arguments["runtime_root"].resolve())
        for env in environments
    )
    assert harness["module"].os.environ["PIPELINE_RUNTIME_DIR"] == "stale-mount"


def test_runtime_can_come_from_pipeline_runtime_dir(harness, monkeypatch) -> None:
    arguments = {**harness["arguments"], "runtime_root": None}
    monkeypatch.setenv(
        "PIPELINE_RUNTIME_DIR", str(harness["arguments"]["runtime_root"])
    )
    result = harness["module"].execute_fixture_acceptance(**arguments)
    assert result["status"] == "complete"


def test_api_uses_environment_when_runtime_argument_is_omitted(harness, monkeypatch):
    arguments = dict(harness["arguments"])
    root = arguments.pop("runtime_root")
    monkeypatch.setenv("PIPELINE_RUNTIME_DIR", str(root))
    result = harness["module"].execute_fixture_acceptance(**arguments)
    assert result["status"] == "complete"


def test_cli_help_explains_the_existing_literal_gate(harness, monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["fixture_acceptance", "--help"])
    with pytest.raises(SystemExit) as caught:
        harness["module"].main()
    assert caught.value.code == 0
    assert EXECUTION_CONFIRMATION in capsys.readouterr().out
    assert harness["events"] == []


def test_missing_runtime_is_rejected_before_services(harness) -> None:
    with pytest.raises(ValueError, match="runtime"):
        harness["module"].execute_fixture_acceptance(
            **{**harness["arguments"], "runtime_root": None}
        )
    assert harness["events"] == []


def test_invalid_metadata_takes_precedence_over_an_existing_root(harness) -> None:
    arguments = harness["arguments"]
    arguments["runtime_root"].mkdir(parents=True)
    _json(arguments["machine_metadata_path"], {})
    with pytest.raises(ValueError, match="machine metadata"):
        harness["module"].execute_fixture_acceptance(**arguments)
    assert harness["events"] == []


def test_modified_matrix_is_rejected_before_creating_runtime(harness) -> None:
    arguments = harness["arguments"]
    matrix = arguments["repository"] / "configs/experiments.toml"
    matrix.write_text(matrix.read_text().replace('"24 hours"', '"12 hours"'))
    with pytest.raises(ValueError, match="fixed coursework policy"):
        harness["module"].execute_fixture_acceptance(**arguments)
    assert not arguments["runtime_root"].exists()
    assert harness["events"] == []


def test_relative_runtime_is_repository_relative(
    harness, monkeypatch, tmp_path
) -> None:
    arguments = {
        **harness["arguments"],
        "runtime_root": Path("reports/runtime/relative"),
    }
    monkeypatch.chdir(tmp_path)
    harness["module"].execute_fixture_acceptance(**arguments)
    assert (
        arguments["repository"] / arguments["runtime_root"] / "fixture-acceptance.json"
    ).is_file()


def test_runtime_outside_repository_is_rejected(harness, tmp_path) -> None:
    root = tmp_path / "outside"
    with pytest.raises(ValueError, match="reports/runtime"):
        harness["module"].execute_fixture_acceptance(
            **{**harness["arguments"], "runtime_root": root}
        )
    assert not root.exists()
    assert harness["events"] == []


def test_diagnostic_write_failure_does_not_mask_primary_failure(
    harness, monkeypatch
) -> None:
    primary = RuntimeError("startup failed")

    def command(command, **kwargs):
        if command.stage == "services_start":
            raise primary
        raise RuntimeError("stop failed")

    def write(path, value):
        raise OSError("diagnostic storage failed")

    monkeypatch.setattr(harness["module"], "_run_command", command)
    monkeypatch.setattr(harness["module"], "_write_new", write)
    with pytest.raises(RuntimeError) as caught:
        harness["module"].execute_fixture_acceptance(**harness["arguments"])
    assert caught.value is primary
    assert any("stop failed" in note for note in primary.__notes__)
    assert any("diagnostic storage failed" in note for note in primary.__notes__)


def test_existing_result_is_never_overwritten_even_if_created_during_gating(
    harness, monkeypatch
) -> None:
    real_recovery = harness["module"]._recovery_equivalence

    def recovery(root):
        result = real_recovery(root)
        _json(root / "fixture-acceptance.json", {"keep": "concurrent writer"})
        return result

    monkeypatch.setattr(harness["module"], "_recovery_equivalence", recovery)
    with pytest.raises(FileExistsError):
        harness["module"].execute_fixture_acceptance(**harness["arguments"])
    path = harness["arguments"]["runtime_root"] / "fixture-acceptance.json"
    assert json.loads(path.read_text()) == {"keep": "concurrent writer"}
    assert harness["commands"][-1].stage == "services_stop"


def test_failed_seal_integrity_prevents_acceptance(harness, monkeypatch) -> None:
    def command(command, **kwargs):
        harness["command"](command, **kwargs)
        if command.stage == "run_seal":
            run_dir = Path(command.argv[command.argv.index("--run-dir") + 1])
            (run_dir / "reports/query-benchmark.json").write_text("tampered")

    monkeypatch.setattr(harness["module"], "_run_command", command)
    with pytest.raises(ValueError, match="integrity"):
        harness["module"].execute_fixture_acceptance(**harness["arguments"])
    assert not any(kind == "gate" for kind, _ in harness["events"])
    assert harness["commands"][-1].stage == "services_stop"


def test_job_proof_requires_both_real_job_identifiers(harness, monkeypatch) -> None:
    real_load = harness["module"].load_finalized_run

    def load(run_dir):
        # Integrity alone is insufficient: remove job evidence and re-seal the double.
        oracle = run_dir / "oracle/hadoop-oracle-manifest.json"
        data = json.loads(oracle.read_text())
        data["jobs"]["aggregate"]["hadoop_job_id"] = None
        _json(oracle, data)
        manifest_path = run_dir / "run-manifest.json"
        manifest = json.loads(manifest_path.read_text())
        descriptor = manifest["artifacts"]["oracle__hadoop-oracle-manifest.json"]
        descriptor.update(sha256=_digest(oracle), byte_size=oracle.stat().st_size)
        _json(manifest_path, manifest)
        (run_dir / "run-manifest.sha256").write_text(_digest(manifest_path))
        return real_load(run_dir)

    monkeypatch.setattr(harness["module"], "load_finalized_run", load)
    with pytest.raises(ValueError, match="job"):
        harness["module"].execute_fixture_acceptance(**harness["arguments"])
    assert not (
        harness["arguments"]["runtime_root"] / "fixture-acceptance.json"
    ).exists()


def test_cli_delegates_without_snapshot_or_plan(harness, monkeypatch, capsys) -> None:
    captured = {}

    def execute(**kwargs):
        captured.update(kwargs)
        return {"status": "mocked"}

    module = harness["module"]
    monkeypatch.setattr(module, "execute_fixture_acceptance", execute)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "fixture_acceptance",
            "--machine-metadata",
            "machine.json",
            "--runtime-root",
            "reports/runtime/fresh",
            "--confirm",
            EXECUTION_CONFIRMATION,
        ],
    )
    assert module.main() == 0
    assert captured["machine_metadata_path"] == Path("machine.json")
    assert captured["runtime_root"] == Path("reports/runtime/fresh")
    assert captured["confirmation"] == EXECUTION_CONFIRMATION
    assert json.loads(capsys.readouterr().out) == {"status": "mocked"}


def test_progress_identifies_each_run_and_stage_before_work(
    harness, monkeypatch, caplog
) -> None:
    caplog.set_level(logging.INFO, logger="iot_energy_pipeline.fixture_acceptance")
    module = harness["module"]
    real_prepare = module._prepare_run
    real_command = harness["command"]

    def prepare(run, snapshot_dir, run_dir):
        assert run["run_id"] in caplog.messages[-1]
        return real_prepare(run, snapshot_dir, run_dir)

    def command(command, **kwargs):
        message = caplog.messages[-1]
        assert command.stage in message
        if command.stage not in {"services_start", "services_stop", "numeric_contract"}:
            assert harness["prepared"][-1]["run_id"] in message
        real_command(command, **kwargs)

    monkeypatch.setattr(module, "_prepare_run", prepare)
    monkeypatch.setattr(module, "_run_command", command)
    module.execute_fixture_acceptance(**harness["arguments"])


@pytest.mark.parametrize(
    "proof", ["missing", "malformed", "failed", "wrong-schema", "not-object"]
)
def test_numeric_contract_must_pass_before_any_fixture_preparation(
    harness, monkeypatch, proof
) -> None:
    root = harness["arguments"]["runtime_root"]
    proof_path = root / "_numeric-contract/numeric-contract.json"

    def command(command, **kwargs):
        harness["command"](command, **kwargs)
        if command.stage == "numeric_contract":
            if proof == "missing":
                proof_path.unlink()
            elif proof == "malformed":
                proof_path.write_text("[")
            elif proof == "not-object":
                proof_path.write_text("[]")
            else:
                document = _mock_numeric_contract()
                if proof == "failed":
                    document["status"] = "failed"
                else:
                    document["schema_version"] = "unsupported"
                _json(proof_path, document)

    monkeypatch.setattr(harness["module"], "_run_command", command)
    with pytest.raises(ValueError, match="numeric contract"):
        harness["module"].execute_fixture_acceptance(**harness["arguments"])
    assert harness["prepared"] == []
    assert [command.stage for command in harness["commands"]] == [
        "services_start",
        "numeric_contract",
        "services_stop",
    ]
    assert not (root / "fixture-acceptance.json").exists()
