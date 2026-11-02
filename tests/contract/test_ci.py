from __future__ import annotations

from pathlib import Path


def test_normal_ci_runs_only_lightweight_test_directories() -> None:
    workflow = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")

    assert "tests/unit tests/property tests/contract" in workflow
    assert "tests/integration" not in workflow
    assert "test_fixture_acceptance" not in workflow


def test_fixture_acceptance_workflow_is_manual_only() -> None:
    workflow = Path(".github/workflows/fixture.yml").read_text(encoding="utf-8")

    assert "workflow_dispatch:" in workflow
    assert "pull_request" not in workflow
    assert "push:" not in workflow
    assert "test_fixture_acceptance.py" in workflow


def test_normal_ci_checks_repository_independence() -> None:
    workflow = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")

    assert "python -m scripts.scan_independence" in workflow


def test_ci_installs_workbook_dependencies_used_by_unit_tests() -> None:
    workflow = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert ".[dev,dataset]" in workflow
