from pathlib import Path

import pytest


@pytest.mark.parametrize("suffix", ["ps1", "sh"])
def test_fixture_acceptance_wrapper_exposes_only_actual_execution_entrypoint(suffix):
    script = Path(f"scripts/execute_fixture_acceptance.{suffix}").read_text("utf-8")
    assert "iot_energy_pipeline.fixture_acceptance" in script
    assert "RUN-DESIGNATED-MACHINE-EXPERIMENTS" in script
    for parameter in (
        "--machine-metadata",
        "--runtime-root",
        "--confirm",
        "--repository",
        "--python",
    ):
        assert parameter in script
    assert "--snapshot-dir" not in script
    assert "--experiment-plan" not in script
    assert "pytest" not in script
    assert "docker compose" not in script  # Ownership and cleanup stay in Python.


def test_wrappers_resolve_repository_from_their_own_location():
    windows = Path("scripts/execute_fixture_acceptance.ps1").read_text("utf-8")
    posix = Path("scripts/execute_fixture_acceptance.sh").read_text("utf-8")
    assert "$PSScriptRoot" in windows
    assert "$LASTEXITCODE" in windows
    assert "PIPELINE_RUNTIME_DIR" in windows
    assert 'dirname -- "$0"' in posix
    assert 'exec "$pipeline_python"' in posix
    assert "PIPELINE_RUNTIME_DIR" in posix
