from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal, Inexact, localcontext
from pathlib import Path
from typing import Any

import pytest

from iot_energy_pipeline.reports import (
    _add_scaled,
    _scaled_exposure,
    _scaled_text,
    build_decision_impact_report,
    build_decision_impact_report_from_ndjson,
    derive_interval_consumption,
    summarize,
)


def _reading(
    index: int,
    value: int,
    *,
    time: str | None = None,
    kind: str = "cumulative_energy",
    unit: str = "kWh",
) -> dict:
    return {
        "source_event_id": f"{index:064x}",
        "meter_id": "meter-a",
        "event_time_utc": time or f"2024-01-01T0{index}:00:00Z",
        "scaled_value": value,
        "decimal_scale": 2,
        "measurement_kind": kind,
        "unit": unit,
    }


def test_interval_derivation_handles_zero_and_negative_deltas_conservatively() -> None:
    result = derive_interval_consumption(
        [
            _reading(0, 1000),
            _reading(1, 1250),
            _reading(2, 1250),
            _reading(3, 1200),
            _reading(4, 1300),
        ]
    )

    assert [row["delta_scaled"] for row in result.intervals] == [250, 0, 100]
    assert [row["delta_kwh"] for row in result.intervals] == ["2.5", "0", "1"]
    assert {row["category"] for row in result.flagged_records} == {
        "first_reading_no_interval",
        "negative_delta_or_reset",
    }


def test_duplicate_timestamp_is_flagged_and_not_used_as_a_baseline() -> None:
    result = derive_interval_consumption(
        [
            _reading(0, 1000),
            _reading(1, 1100, time="2024-01-01T01:00:00Z"),
            _reading(2, 1200, time="2024-01-01T01:00:00Z"),
            _reading(3, 1300, time="2024-01-01T02:00:00Z"),
            _reading(4, 1400, time="2024-01-01T03:00:00Z"),
        ]
    )

    assert [row["delta_scaled"] for row in result.intervals] == [100]
    assert result.intervals[0]["interval_end_utc"] == "2024-01-01T03:00:00Z"
    categories = [row["category"] for row in result.flagged_records]
    assert categories.count("ambiguous_duplicate_timestamp") == 2
    assert "first_after_ambiguous_timestamp" in categories


@pytest.mark.parametrize(
    "kind,unit",
    [("UNKNOWN", "kWh"), ("power", "kW"), ("cumulative_energy", "UNKNOWN")],
)
def test_unverified_semantics_never_produce_consumption(kind: str, unit: str) -> None:
    result = derive_interval_consumption(
        [_reading(0, 100, kind=kind, unit=unit), _reading(1, 200, kind=kind, unit=unit)]
    )
    assert result.intervals == ()
    assert all(
        row["category"] == "unverified_cumulative_kwh_semantics"
        for row in result.flagged_records
    )


def test_decision_impact_report_labels_hypothetical_scenarios_and_residual() -> None:
    verified = [_reading(0, 1000), _reading(1, 1100), _reading(2, 1200)]
    candidate = [verified[0], verified[2]]

    report = build_decision_impact_report(
        candidate,
        verified,
        reconciliation_passed=True,
        verification_seconds=4.25,
        candidate_storage_bytes=1000,
        verification_storage_bytes=250,
    )

    assert report["affected_meter_period_count"] == 2
    assert report["absolute_kwh_discrepancy"] == "0"
    assert report["verification_seconds"] == 4.25
    assert report["storage_overhead_bytes"] == 250
    assert report["storage_overhead_ratio"] == 0.25
    assert [row["normalized_rate"] for row in report["tariff_scenarios"]] == [
        "0.5",
        "1.0",
        "2.0",
    ]
    assert all(
        row["label"] == "hypothetical normalized tariff scenario"
        and row["residual_exposure_after_verification"] is None
        for row in report["tariff_scenarios"]
    )


def test_business_report_refuses_unreconciled_results() -> None:
    with pytest.raises(ValueError, match="passing Spark-Hadoop reconciliation"):
        build_decision_impact_report(
            [_reading(0, 1)],
            [_reading(0, 1)],
            reconciliation_passed=False,
            verification_seconds=1,
            candidate_storage_bytes=1,
            verification_storage_bytes=1,
        )


def test_disk_backed_decision_report_matches_exact_interval_semantics(
    tmp_path: Path,
) -> None:
    verified = [_reading(0, 1000), _reading(1, 1100), _reading(2, 1200)]
    candidate = [verified[0], verified[2]]
    candidate_path = tmp_path / "candidate.ndjson"
    verified_path = tmp_path / "verified.ndjson"
    for path, records in ((candidate_path, candidate), (verified_path, verified)):
        path.write_text(
            "".join(
                json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n"
                for record in records
            ),
            encoding="utf-8",
        )

    report = build_decision_impact_report_from_ndjson(
        candidate_path,
        verified_path,
        candidate_record_count=2,
        verified_record_count=3,
        scratch_directory=tmp_path,
        reconciliation_passed=True,
        verification_seconds=4.25,
        candidate_storage_bytes=1000,
        verification_storage_bytes=250,
    )

    assert report["affected_meter_period_count"] == 2
    assert report["absolute_kwh_discrepancy"] == "0"
    assert report["candidate_flagged_record_count"] == 1
    assert report["verified_flagged_record_count"] == 1


def test_disk_backed_report_matches_in_memory_duplicate_and_reset_rules(
    tmp_path: Path,
) -> None:
    verified = [
        _reading(0, 1000),
        _reading(1, 1100, time="2024-01-01T01:00:00Z"),
        _reading(2, 1200, time="2024-01-01T01:00:00Z"),
        _reading(3, 900, time="2024-01-01T02:00:00Z"),
        _reading(4, 1000, time="2024-01-01T03:00:00Z"),
    ]
    candidate = [verified[index] for index in (0, 1, 3, 4)]
    paths = (tmp_path / "candidate.ndjson", tmp_path / "verified.ndjson")
    for path, records in zip(paths, (candidate, verified), strict=True):
        path.write_text(
            "".join(
                json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n"
                for record in records
            ),
            encoding="utf-8",
        )
    expected = build_decision_impact_report(
        candidate,
        verified,
        reconciliation_passed=True,
        verification_seconds=2.0,
        candidate_storage_bytes=10,
        verification_storage_bytes=20,
    )

    actual = build_decision_impact_report_from_ndjson(
        paths[0],
        paths[1],
        candidate_record_count=len(candidate),
        verified_record_count=len(verified),
        scratch_directory=tmp_path,
        reconciliation_passed=True,
        verification_seconds=2.0,
        candidate_storage_bytes=10,
        verification_storage_bytes=20,
    )

    assert actual == expected


def test_performance_summary_requires_real_measurements() -> None:
    assert summarize([3.0, 1.0, 2.0]) == {
        "median": 2.0,
        "minimum": 1.0,
        "maximum": 3.0,
    }
    with pytest.raises(ValueError):
        summarize([])
    assert Decimal("0.1") + Decimal("0.2") == Decimal("0.3")


def _both_reports(
    tmp_path: Path, candidate: list[dict], verified: list[dict]
) -> dict[str, Any]:
    options: dict[str, Any] = {
        "reconciliation_passed": True,
        "verification_seconds": 2.0,
        "candidate_storage_bytes": 10,
        "verification_storage_bytes": 20,
    }
    paths = (tmp_path / "candidate.ndjson", tmp_path / "verified.ndjson")
    for path, records in zip(paths, (candidate, verified), strict=True):
        path.write_text(
            "".join(json.dumps(record) + "\n" for record in records), "utf-8"
        )
    local = build_decision_impact_report(candidate, verified, **options)
    disk = build_decision_impact_report_from_ndjson(
        *paths,
        candidate_record_count=len(candidate),
        verified_record_count=len(verified),
        scratch_directory=tmp_path,
        **options,
    )
    assert disk == local
    assert not list(tmp_path.glob(".decision-impact.*"))
    return local


def test_missing_middlepoint_has_no_comparable_energy(tmp_path: Path) -> None:
    verified = [
        _reading(i, value * 100, time=f"2024-01-01T00:{minute:02d}:00Z")
        for i, (minute, value) in enumerate(((0, 100), (15, 110), (30, 120)))
    ]
    report = _both_reports(tmp_path, [verified[0], verified[2]], verified)
    assert report["absolute_kwh_discrepancy"] == "0"
    assert report["affected_meter_period_count"] == 2
    assert report["incomparable_meter_period_count"] == 2
    assert report["comparable_meter_period_count"] == 0
    first, second = report["affected_meter_periods"]
    assert first["comparison_status"] == "candidate_unavailable"
    assert first["candidate_kwh"] is None
    assert first["verified_kwh"] == "10"
    assert second["comparison_status"] == "temporal_support_mismatch"
    assert second["candidate_interval_start_utc"] == verified[0]["event_time_utc"]
    assert second["verified_interval_start_utc"] == verified[1]["event_time_utc"]
    assert (second["candidate_kwh"], second["verified_kwh"]) == ("20", "10")
    assert all(
        p["absolute_kwh_discrepancy"] is None for p in report["affected_meter_periods"]
    )
    assert [s["gross_exposure"] for s in report["tariff_scenarios"]] == ["0"] * 3
    assert all(
        s["residual_exposure_after_verification"] is None
        for s in report["tariff_scenarios"]
    )


def test_actual_restrictive_fixture_ambiguity_is_unknown_not_zero(
    tmp_path: Path,
) -> None:
    # Physical rows from acceptance-final-20261027-001/watermark-restrictive-r01.
    witnesses = [
        (
            "52a351279189af4b78e484efa620e6fc6bf14599be2557d548cf76fde84a239d",
            0,
            26728700000000000000,
        ),
        (
            "07c64322fd4174ba2ab770b5844f93aa0071f32d5d7987aae5154d1dde10818b",
            15,
            26729700000000000000,
        ),
        (
            "9e2fff0ef1495d243568235bff33212e851ecdc83434d02960927f492bd9ff90",
            15,
            26729700000000000000,
        ),
        (
            "913d2e86b128a18e576c77c60ba2698dbf1ad248edd1c3706be212a80830008f",
            30,
            26730700000000000000,
        ),
        (
            "0eae6e472cecdc5721a06444e0158a7be187279b68c69cebfbc9a69d87fb247c",
            45,
            26731700000000000000,
        ),
    ]
    verified = [
        dict(
            _reading(i, value, time=f"2023-12-31T17:{minute:02d}:00.000000Z"),
            source_event_id=source_id,
            decimal_scale=15,
        )
        for i, (source_id, minute, value) in enumerate(witnesses)
    ]
    candidate = [r for i, r in enumerate(verified) if i != 2]
    report = _both_reports(tmp_path, candidate, verified)
    assert report["absolute_kwh_discrepancy"] == "0"
    assert report["affected_meter_period_count"] == 2
    assert report["comparable_meter_period_count"] == 1
    assert report["incomparable_meter_period_count"] == 2
    for period in report["affected_meter_periods"]:
        assert period["comparison_status"] == "verified_unavailable"
        assert period["candidate_kwh"] == "1"
        assert period["verified_kwh"] is None
        assert period["verified_interval_start_utc"] is None
        assert period["absolute_kwh_discrepancy"] is None
    categories = [r["category"] for r in report["verified_flagged_records"]]
    assert categories.count("ambiguous_duplicate_timestamp") == 2
    assert categories.count("first_after_ambiguous_timestamp") == 1
    assert all(
        s["residual_exposure_after_verification"] is None
        for s in report["tariff_scenarios"]
    )


@pytest.mark.parametrize("reverse", [False, True])
def test_absent_zero_interval_is_changed_coverage(
    tmp_path: Path,
    reverse: bool,
) -> None:
    complete = [_reading(0, 100), _reading(1, 100), _reading(2, 100)]
    sparse = [complete[0], complete[2]]
    candidate, verified = (complete, sparse) if reverse else (sparse, complete)
    report = _both_reports(tmp_path, candidate, verified)
    assert report["affected_meter_period_count"] == 2
    assert report["numeric_discrepancy_meter_period_count"] == 0
    assert report["incomparable_meter_period_count"] == 2
    assert report["absolute_kwh_discrepancy"] == "0"
    side = "verified" if reverse else "candidate"
    first = report["affected_meter_periods"][0]
    assert first["comparison_status"] == f"{side}_unavailable"
    assert first[f"{side}_kwh"] is None


def test_comparable_difference_and_unknown_coverage_have_separate_totals(
    tmp_path: Path,
) -> None:
    verified = [_reading(i, value) for i, value in enumerate((100, 200, 300, 400))]
    candidate = [dict(row) for row in verified if row != verified[1]]
    candidate[-1]["scaled_value"] = 450
    report = _both_reports(tmp_path, candidate, verified)
    assert report["affected_meter_period_count"] == 3
    assert report["comparable_meter_period_count"] == 1
    assert report["numeric_discrepancy_meter_period_count"] == 1
    assert report["incomparable_meter_period_count"] == 2
    assert report["absolute_kwh_discrepancy"] == "0.5"
    assert [s["gross_exposure"] for s in report["tariff_scenarios"]] == [
        "0.25",
        "0.5",
        "1",
    ]


@pytest.mark.parametrize("invalid", ["contract", "timestamp", "coefficient"])
def test_invalid_verified_series_does_not_zero_fill_candidate_energy(
    tmp_path: Path,
    invalid: str,
) -> None:
    candidate = [_reading(0, 100), _reading(1, 200), _reading(2, 300)]
    verified = [dict(row) for row in candidate]
    field, value = {
        "contract": ("unit", "UNKNOWN"),
        "timestamp": ("event_time_utc", "invalid"),
        "coefficient": ("scaled_value", True),
    }[invalid]
    verified[1][field] = value
    report = _both_reports(tmp_path, candidate, verified)
    assert report["candidate_interval_count"] == 2
    assert report["verified_interval_count"] == 0
    assert report["incomparable_meter_period_count"] == 2
    assert report["verified_flagged_record_count"] > 0
    assert report["absolute_kwh_discrepancy"] == "0"
    assert all(p["verified_kwh"] is None for p in report["affected_meter_periods"])


@pytest.mark.parametrize(
    "mode", ["unchanged", "ambiguous", "reset", "invalid", "empty"]
)
def test_unchanged_exclusions_do_not_fabricate_affected_periods(
    tmp_path: Path,
    mode: str,
) -> None:
    rows = [_reading(0, 100), _reading(1, 100)]
    if mode == "ambiguous":
        rows.append(dict(rows[-1], source_event_id="another physical row"))
    elif mode == "reset":
        rows[-1]["scaled_value"] = 0
    elif mode == "invalid":
        rows[-1]["unit"] = "UNKNOWN"
    elif mode == "empty":
        rows = []
    report = _both_reports(tmp_path, rows, rows)
    assert report["affected_meter_period_count"] == 0
    assert report["incomparable_meter_period_count"] == 0
    assert report["comparable_meter_period_count"] == (1 if mode == "unchanged" else 0)
    assert report["coverage_limits"]
    assert all(
        s["residual_exposure_after_verification"] is None
        for s in report["tariff_scenarios"]
    )


def test_d0779_wide_scaled_reading_survives_disk_report(tmp_path: Path) -> None:
    # Actual 26724.7 reading at observed scale 15 exceeds SQLite's int64.
    witness = 26724700000000000000
    verified = [_reading(i, witness + i * 10**15) for i in range(3)]
    for row in verified:
        row.update(meter_id="D0779", decimal_scale=15)
    candidate = [
        dict(row, scaled_value=witness + i * 2 * 10**15)
        for i, row in enumerate(verified)
    ]
    report = _both_reports(tmp_path, candidate, verified)
    assert report["absolute_kwh_discrepancy"] == "2"
    assert [r["gross_exposure"] for r in report["tariff_scenarios"]] == ["1", "2", "4"]


@pytest.mark.parametrize("precision", [6, 28])
@pytest.mark.parametrize("scale", range(19))
def test_38_digit_reports_are_exact_at_every_observed_scale(
    tmp_path: Path, precision: int, scale: int
) -> None:
    wide = 10**38 - 1
    verified = [_reading(0, 0), _reading(1, wide), _reading(2, wide)]
    for row in verified:
        row["decimal_scale"] = scale

    # Independent expected strings: no context-sensitive Decimal arithmetic.
    def text(value: int, places: int) -> str:
        digits = str(value).zfill(places + 1)
        return (
            (digits[:-places] + "." + digits[-places:]).rstrip("0").rstrip(".")
            if places
            else digits
        )

    with localcontext() as context:
        context.prec = precision
        context.traps[Inexact] = True
        before = context.copy()
        intervals = derive_interval_consumption(verified)
        assert intervals.intervals[0]["delta_kwh"] == text(wide, scale)
        candidate = [
            dict(row, scaled_value=value)
            for row, value in zip(verified, (0, 0, wide), strict=True)
        ]
        report = _both_reports(tmp_path, candidate, verified)
        assert report["absolute_kwh_discrepancy"] == text(2 * wide, scale)
        assert [r["gross_exposure"] for r in report["tariff_scenarios"]] == [
            text(wide, scale),
            text(2 * wide, scale),
            text(4 * wide, scale),
        ]
        assert context.prec == before.prec
        assert context.traps == before.traps
        assert context.flags == before.flags


def test_wide_reports_align_scales_and_continue_after_flags(tmp_path: Path) -> None:
    wide = 10**38 - 1
    verified = [
        _reading(0, -wide),
        _reading(1, wide),
        _reading(2, 0),  # Reset: next interval must use this new baseline.
        _reading(3, wide),
        _reading(4, 1, time="2024-01-01T04:00:00Z"),
        _reading(5, 2, time="2024-01-01T04:00:00Z"),
        _reading(6, 0),
        _reading(7, wide),
    ]
    candidate = [dict(row, decimal_scale=0) for row in verified]
    for row in verified:
        row["decimal_scale"] = 18
    with localcontext() as context:
        context.prec = 6
        context.traps[Inexact] = True
        report = _both_reports(tmp_path, candidate, verified)
    with localcontext() as reference:
        reference.prec = 100
        expected = 4 * Decimal(wide) * (1 - Decimal("1e-18"))
        assert Decimal(report["absolute_kwh_discrepancy"]) == expected
        for scenario in report["tariff_scenarios"]:
            assert Decimal(scenario["gross_exposure"]) == (
                expected * Decimal(scenario["normalized_rate"])
            )
    categories = [row["category"] for row in report["verified_flagged_records"]]
    assert categories.count("negative_delta_or_reset") == 1
    assert categories.count("ambiguous_duplicate_timestamp") == 2
    assert categories.count("first_after_ambiguous_timestamp") == 1
    assert report["affected_meter_period_count"] == 3


def test_exact_accumulator_at_five_million_periods_with_scale_change() -> None:
    wide = 10**38 - 1
    # Represent the prior subtotal directly instead of allocating 5M records.
    with localcontext() as context:
        context.prec = 6
        context.traps[Inexact] = True
        total = _add_scaled((wide * 4_999_999, 0), (wide, 18))
        actual = _scaled_text(*total)
        exposures = [
            _scaled_exposure(total, Decimal(rate)) for rate in ("0.5", "1.0", "2.0")
        ]
    with localcontext() as reference:
        reference.prec = 100
        expected = Decimal(wide) * 4_999_999 + Decimal(wide) * Decimal("1e-18")
        assert Decimal(actual) == expected
        assert [Decimal(value) for value in exposures] == [
            expected * Decimal(rate) for rate in ("0.5", "1.0", "2.0")
        ]


def test_wide_disk_report_crosses_ingest_batch_boundary(tmp_path: Path) -> None:
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    verified = [
        dict(
            _reading(i, 10**38 - 1003 + i),
            decimal_scale=18,
            event_time_utc=(start + timedelta(seconds=i)).isoformat(),
        )
        for i in range(1003)
    ]
    with localcontext() as context:
        context.prec = 6
        context.traps[Inexact] = True
        candidate = [
            dict(row, scaled_value=verified[0]["scaled_value"]) for row in verified
        ]
        report = _both_reports(tmp_path, candidate, verified)
    assert report["affected_meter_period_count"] == 1002
    assert report["absolute_kwh_discrepancy"] == "0.000000000000001002"
