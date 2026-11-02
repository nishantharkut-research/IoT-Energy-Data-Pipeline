from __future__ import annotations

import json
from pathlib import Path

import pytest

from iot_energy_pipeline.course_report import (
    _validate_run_configuration,
    generate_course_report,
    render_course_report,
)


def test_course_report_renders_measured_results_with_scenario_guardrail() -> None:
    results = {
        "status": "complete",
        "experiment_plan_sha256": "a" * 64,
        "machine_metadata_sha256": "b" * 64,
        "snapshot_manifest_sha256": "c" * 64,
        "runs": [
            {
                "run_id": "correctness-combined-r01",
                "experiment": "correctness",
                "event_count": "fixture",
                "status": "finalized",
                "workflow_seconds": 8.0,
            }
        ],
        "performance_summary": [
            {
                "event_count": 100000,
                "repetitions": 3,
                "metrics": {
                    "workflow_seconds": {
                        "median": 10.0,
                        "minimum": 9.0,
                        "maximum": 11.0,
                    }
                },
            }
        ],
        "correctness_semantic_equivalence": {"status": "identical"},
        "recovery_semantic_equivalence": {"status": "identical"},
        "watermark_effect": {
            "gold_status": "identical",
            "candidate_difference_exposed": True,
        },
    }
    decisions = {
        "correctness-combined-r01": {
            "affected_meter_period_count": 1,
            "absolute_kwh_discrepancy": "2",
            "verification_seconds": 4.5,
            "tariff_scenarios": [{"normalized_rate": "1.0", "gross_exposure": "2"}],
        }
    }

    report = render_course_report(results, decisions)

    assert "100,000" in report
    assert "median" in report.lower()
    assert "Recovery records | identical" in report
    assert "Fault schedules | identical" in report
    assert "Restrictive watermark | candidate difference exposed" in report
    assert "not an HKUST financial result" in report
    assert "correctness-combined-r01" in report


def test_course_report_refuses_incomplete_results() -> None:
    with pytest.raises(ValueError, match="complete experiment results"):
        render_course_report({"status": "running"}, {})


def test_complete_label_cannot_publish_an_empty_unbound_matrix(tmp_path: Path) -> None:
    results = {
        "schema_version": "experiment-results-v1",
        "status": "complete",
        "runs": [],
        "performance_summary": [],
        "correctness_semantic_equivalence": {"status": "identical"},
        "recovery_semantic_equivalence": {"status": "identical"},
        "watermark_effect": {"candidate_difference_exposed": True},
    }
    source = tmp_path / "results.json"
    source.write_text(json.dumps(results))
    output = tmp_path / "report.md"
    with pytest.raises(ValueError, match="evidence|binding|matrix"):
        generate_course_report(
            experiment_results_path=source, runtime_root=tmp_path, output=output
        )
    assert not output.exists()


@pytest.mark.parametrize("wrong", ["event_count", "repetition", "watermark"])
def test_publication_checks_executed_configuration_not_just_result_labels(
    wrong: str,
) -> None:
    planned = {
        "run_id": "scale-100000-r02",
        "event_count": 100000,
        "repetition": 2,
        "fault": "clean",
        "seed": 42,
        "partition_count": 3,
        "watermark": "24 hours",
        "max_offsets_per_trigger": 10000,
    }
    distributed = {
        k: planned[k]
        for k in (
            "run_id",
            "fault",
            "seed",
            "partition_count",
            "watermark",
            "max_offsets_per_trigger",
        )
    }
    distributed["canonical_event_count"] = 100000
    gold = {"source_coverage_count": 100000}
    replay = {"repetition": 2, "requested_event_count": 100000}
    _validate_run_configuration(planned, distributed, gold, replay)
    if wrong == "event_count":
        distributed["canonical_event_count"] = 144
        gold["source_coverage_count"] = 144
        replay["requested_event_count"] = 144
    elif wrong == "repetition":
        replay["repetition"] = 1
    else:
        distributed["watermark"] = "1 minute"
    with pytest.raises(ValueError, match="executed|configuration"):
        _validate_run_configuration(planned, distributed, gold, replay)
