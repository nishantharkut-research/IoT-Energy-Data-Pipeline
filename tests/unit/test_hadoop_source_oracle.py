from __future__ import annotations

import hashlib
import json
from decimal import localcontext
from pathlib import Path

import pytest

from jobs.hadoop.distributed_oracle import _validate_oracle_file
from jobs.hadoop.reconcile import reconcile_source_records
from jobs.hadoop.record_mapper import map_source_record
from jobs.hadoop.record_reducer import reduce_source_records


def _event(**changes: object) -> dict[str, object]:
    locator = "fixture-v1|clean|readings.xlsx|Readings|2"
    source_id = hashlib.sha256(locator.encode("utf-8")).hexdigest()
    event: dict[str, object] = {
        "schema_version": "canonical-event-v1",
        "dataset_version": "fixture-v1",
        "source_variant": "clean",
        "source_event_id": source_id,
        "source_relative_path": "readings.xlsx",
        "workbook_sheet": "Readings",
        "source_row_number": 2,
        "meter_id": "meter-a",
        "brick_entity_id": "https://example.test/meter-a",
        "brick_building_ids": [
            "https://example.test/building-a",
            "https://example.test/building-b",
        ],
        "brick_zone_ids": ["https://example.test/zone-a"],
        "brick_metered_entities": [
            {
                "entity_id": "https://example.test/panel-a",
                "type_uris": ["https://brickschema.org/schema/Brick#Equipment"],
            }
        ],
        "brick_unit_uri": "http://qudt.org/vocab/unit/KiloW-HR",
        "brick_usage_type": "Normal",
        "original_timestamp_text": "2024-01-01T00:00:00",
        "source_timezone": "Asia/Hong_Kong",
        "event_time_utc": "2023-12-31T16:00:00Z",
        "original_numeric_text": "10.00",
        "scaled_value": 1000,
        "decimal_scale": 2,
        "measurement_kind": "cumulative_energy",
        "unit": "kWh",
        "quality_flags": [],
    }
    return event | changes


def test_source_mapper_recomputes_identity_and_preserves_every_field() -> None:
    event = _event()

    key, mapped = map_source_record(event)

    assert key == event["source_event_id"]
    assert mapped == event
    assert mapped is not event


@pytest.mark.parametrize(
    ("text", "scale", "scaled"),
    [
        ("26724.7", 15, 26724700000000000000),
        (str(10**38 - 1), 0, 10**38 - 1),
        (str(-(10**38 - 1)), 0, -(10**38 - 1)),
    ],
)
def test_independent_record_mapper_preserves_wide_integers(
    text: str, scale: int, scaled: int
) -> None:
    event = _event(original_numeric_text=text, decimal_scale=scale, scaled_value=scaled)
    with localcontext() as context:
        context.prec = 6
        _, mapped = map_source_record(json.loads(json.dumps(event)))
    assert mapped == event
    assert type(mapped["scaled_value"]) is int


@pytest.mark.parametrize("scaled", [10**38, -(10**38)])
def test_record_mapper_rejects_decimal38_overflow(scaled: int) -> None:
    with pytest.raises(ValueError, match="bounds"):
        map_source_record(
            _event(
                original_numeric_text=str(scaled), decimal_scale=0, scaled_value=scaled
            )
        )


def test_record_mapper_source_comparison_never_rounds() -> None:
    with pytest.raises(ValueError, match="scaled numeric"):
        map_source_record(
            _event(
                original_numeric_text=str(10**37) + ".1",
                decimal_scale=0,
                scaled_value=10**37,
            )
        )


@pytest.mark.parametrize(
    "change,match",
    [
        ({"source_event_id": "0" * 64}, "source_event_id does not match"),
        ({"unexpected": "field"}, "canonical field set"),
        (
            {"brick_building_ids": list(reversed(_event()["brick_building_ids"]))},
            "sorted",
        ),
        ({"quality_flags": ["same", "same"]}, "unique"),
        ({"original_numeric_text": "10.01"}, "scaled numeric"),
    ],
)
def test_source_mapper_fails_closed_on_exact_contract_violation(
    change: dict[str, object], match: str
) -> None:
    with pytest.raises((TypeError, ValueError), match=match):
        map_source_record(_event(**change))


def test_source_reducer_requires_one_record_per_source_identity() -> None:
    key, mapped = map_source_record(_event())

    assert reduce_source_records(key, [mapped]) == mapped
    with pytest.raises(ValueError, match="duplicate source_event_id"):
        reduce_source_records(key, [mapped, mapped])


def test_source_reconciliation_is_field_exact() -> None:
    first = _event()
    changed = _event(scaled_value=999)

    assert reconcile_source_records([first], [first]) == []
    errors = reconcile_source_records([first], [changed])
    assert errors == [
        f"{first['source_event_id']}.scaled_value: expected 1000, got 999"
    ]


def test_distributed_oracle_validates_sorted_output_from_disk(tmp_path: Path) -> None:
    output = tmp_path / "oracle.ndjson"
    records = [
        {"source_event_id": "a" * 64},
        {"source_event_id": "b" * 64},
    ]
    output.write_text(
        "".join(json.dumps(record) + "\n" for record in records),
        encoding="utf-8",
    )

    assert (
        _validate_oracle_file(
            output, key_field="source_event_id", label="source-record oracle"
        )
        == 2
    )

    output.write_text(
        json.dumps(records[0]) + "\n" + json.dumps(records[0]) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="duplicate or unsorted"):
        _validate_oracle_file(
            output, key_field="source_event_id", label="source-record oracle"
        )
