from __future__ import annotations

import hashlib
import json
from datetime import datetime
from decimal import Decimal, Inexact, Rounded, localcontext
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile

import pytest
from openpyxl import Workbook, load_workbook

import iot_energy_pipeline.canonicalize as canonicalize_module
from iot_energy_pipeline.canonicalize import (
    CanonicalizationRules,
    MeasurementRule,
    build_snapshot,
    canonicalize_workbook,
)
from iot_energy_pipeline.manifests import register_dataset
from iot_energy_pipeline.source_layout import (
    SourceLayoutRules,
    WorkbookLayoutRule,
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _xml_source(tmp_path: Path, numeric_text: str, *, boolean_cell: str | None = None):
    """Inject a decimal directly: saving a Python float would lose the regression."""
    manifest = _source(tmp_path)
    path = manifest._root / "readings.xlsx"
    with ZipFile(path) as archive:
        entries = {name: archive.read(name) for name in archive.namelist()}
    namespace = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
    sheet = ET.fromstring(entries["xl/worksheets/sheet1.xml"])
    for coordinate, text in (("A2", "45292.000000000000"), ("C2", numeric_text)):
        cell = sheet.find(f".//{namespace}c[@r='{coordinate}']")
        cell.clear()
        cell.attrib.update(r=coordinate, t="n")
        if coordinate == "A2":
            cell.set("s", "1")
        ET.SubElement(cell, namespace + "v").text = text
    if boolean_cell is not None:
        cell = sheet.find(f".//{namespace}c[@r='{boolean_cell}']")
        cell.clear()
        cell.attrib.update(r=boolean_cell, t="b")
        ET.SubElement(cell, namespace + "v").text = numeric_text
    entries["xl/worksheets/sheet1.xml"] = ET.tostring(sheet)
    with ZipFile(path, "w") as archive:
        for name, data in entries.items():
            archive.writestr(name, data)
    return register_dataset(
        manifest._root,
        tmp_path / "xml-manifest.json",
        dataset_version="fixture-v1",
        source_variant="clean",
    )


@pytest.mark.parametrize("text", ["0", "1"])
@pytest.mark.parametrize(
    ("coordinate", "category", "provenance_field"),
    [
        ("A2", "invalid_timestamp", "original_timestamp_text"),
        ("C2", "invalid_numeric_value", "original_numeric_text"),
    ],
)
def test_snapshot_rejects_boolean_cells_and_keeps_their_xml_text(
    tmp_path: Path, text: str, coordinate: str, category: str, provenance_field: str
) -> None:
    manifest = _xml_source(tmp_path, text, boolean_cell=coordinate)

    result = build_snapshot(manifest, tmp_path / "snapshot", _rules())

    assert all(e["source_row_number"] != 2 for e in result.events)
    row = next(r for r in result.source_quality if r["source_row_number"] == 2)
    assert row["category"] == category
    assert row[provenance_field] == text


def test_snapshot_uses_exact_numeric_xml_and_preserves_excel_serial(tmp_path: Path):
    manifest = _xml_source(tmp_path, "0.123456789012345678")
    rules = _rules().with_measurement(
        "meter-a", MeasurementRule("cumulative_energy", "kWh", 18, "fixture")
    )

    result = build_snapshot(manifest, tmp_path / "snapshot", rules)

    event = next(e for e in result.events if e["source_row_number"] == 2)
    assert event["scaled_value"] == 123456789012345678
    assert event["original_numeric_text"] == "0.123456789012345678"
    assert event["original_timestamp_text"] == "45292.000000000000"
    assert event["event_time_utc"] == "2023-12-31T16:00:00.000000Z"
    import pyarrow.parquet as pq

    assert pq.read_table(tmp_path / "snapshot/canonical.parquet").to_pylist() == [
        json.loads(line)
        for line in (tmp_path / "snapshot/canonical.ndjson").read_text().splitlines()
    ]


@pytest.mark.parametrize(
    ("text", "scale", "expected"),
    [
        ("26724.7", 15, 26724700000000000000),
        (str(10**38 - 1), 0, 10**38 - 1),
        (str(-(10**38 - 1)), 0, -(10**38 - 1)),
    ],
)
def test_snapshot_keeps_wide_integers_in_json_and_decimal128_in_parquet(
    tmp_path: Path, text: str, scale: int, expected: int
) -> None:
    import pyarrow.parquet as pq

    manifest = _xml_source(tmp_path, text)
    rules = _rules().with_measurement(
        "meter-a", MeasurementRule("cumulative_energy", "kWh", scale, "fixture")
    )
    with localcontext() as context:
        context.prec = 6
        context.traps[Inexact] = True
        context.traps[Rounded] = True
        result = build_snapshot(manifest, tmp_path / "snapshot", rules)
        event = next(e for e in result.events if e["source_row_number"] == 2)
        assert event["scaled_value"] == expected
        assert type(event["scaled_value"]) is int
        assert all(r["source_row_number"] != 2 for r in result.source_quality)
        lines = (tmp_path / "snapshot/canonical.ndjson").read_text().splitlines()
        json_rows = [json.loads(line) for line in lines]
        assert all(type(r["scaled_value"]) is int for r in json_rows)
        parquet_rows = pq.read_table(
            tmp_path / "snapshot/canonical.parquet"
        ).to_pylist()
        assert all(type(r["scaled_value"]) is Decimal for r in parquet_rows)
        assert [
            dict(r, scaled_value=int(r["scaled_value"])) for r in parquet_rows
        ] == json_rows
        # Also exercise the direct writer; snapshots normally use its SQLite variant.
        canonicalize_module._write_parquet([event], tmp_path / "direct.parquet")
        assert pq.read_table(tmp_path / "direct.parquet").to_pylist()[0][
            "scaled_value"
        ] == Decimal(expected)


@pytest.mark.parametrize(
    ("text", "scale", "category"),
    [
        ("0.123456789012345678", 17, "invalid_numeric_value"),
        (str(10**38), 0, "numeric_overflow"),
        ("1.00000000000000000000000000001", 0, "invalid_numeric_value"),
        (" 0.123456789012345678 ", 17, "invalid_numeric_value"),
        ("1E-10000000", 0, "invalid_numeric_value"),
    ],
)
def test_snapshot_rejects_inexact_scale_or_overflow_with_raw_provenance(
    tmp_path: Path, text: str, scale: int, category: str
):
    manifest = _xml_source(tmp_path, text)
    rules = _rules().with_measurement(
        "meter-a", MeasurementRule("cumulative_energy", "kWh", scale, "fixture")
    )

    result = build_snapshot(manifest, tmp_path / "snapshot", rules)

    row = next(r for r in result.source_quality if r["source_row_number"] == 2)
    assert row["category"] == category
    assert row["original_numeric_text"] == text
    assert row["original_timestamp_text"] == "45292.000000000000"


def test_snapshot_does_not_materialize_results_above_the_return_boundary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest = _source(tmp_path)
    monkeypatch.setattr(
        canonicalize_module, "_SNAPSHOT_RESULT_MATERIALIZATION_LIMIT", 2
    )

    result = build_snapshot(manifest, tmp_path / "snapshot", _rules())

    assert result.event_count == 3
    assert result.events is None
    assert (
        len((tmp_path / "snapshot/canonical.ndjson").read_text("utf-8").splitlines())
        == 3
    )


def _source(tmp_path: Path, *, variant: str = "clean"):
    root = tmp_path / variant
    root.mkdir()
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Readings"
    sheet.append(["timestamp", "meter_id", "value"])
    sheet.append([datetime(2024, 1, 1, 0, 0), "meter-a", "10.00"])
    sheet.append([datetime(2024, 1, 1, 0, 0), "meter-a", "10.00"])
    sheet.append([datetime(2024, 1, 1, 0, 15), "meter-a", None])
    sheet.append([datetime(2024, 1, 1, 0, 30), "meter-a", "not-a-number"])
    sheet.append([datetime(2024, 1, 1, 0, 45), "meter-b", "2.50"])
    workbook.save(root / "readings.xlsx")
    (root / "metadata.ttl").write_text(
        """\
@prefix brick: <https://brickschema.org/schema/Brick#> .
@prefix ref: <https://brickschema.org/schema/Brick/ref#> .
@prefix unit: <http://qudt.org/vocab/unit/> .
@prefix ex: <https://example.test/> .
ex:meter-entity a brick:Electrical_Meter ;
  brick:hasUnit unit:KiloW-HR ;
  ref:hasExternalReference [ ref:hasTimeseriesId "meter-a" ] .
ex:building-a a brick:Building ; brick:hasPart ex:zone-a .
ex:zone-a a brick:Zone ; brick:hasPart ex:meter-entity .
ex:panel-a a brick:Equipment ; brick:isMeteredBy ex:meter-entity .
""",
        encoding="utf-8",
    )
    return register_dataset(
        root,
        tmp_path / f"{variant}-dataset-manifest.json",
        dataset_version="fixture-v1",
        source_variant=variant,  # type: ignore[arg-type]
    )


def _rules() -> CanonicalizationRules:
    evidence = "synthetic fixture declaration"
    return CanonicalizationRules(
        source_timezone="Asia/Hong_Kong",
        timezone_evidence=evidence,
        source_layout=SourceLayoutRules(
            rules=(
                WorkbookLayoutRule(
                    name="synthetic-long-format",
                    relative_path_pattern=r"readings\.xlsx",
                    sheet_name="Readings",
                    header_row=1,
                    expected_columns=("timestamp", "meter_id", "value"),
                    timestamp_column="timestamp",
                    value_column="value",
                    meter_id_column="meter_id",
                    evidence=evidence,
                ),
            ),
            evidence=evidence,
        ),
        measurements={
            "meter-a": MeasurementRule(
                "cumulative_energy", "kWh", 2, evidence, "KiloW-HR"
            ),
            "meter-b": MeasurementRule("cumulative_energy", "kWh", 2, evidence, None),
        },
    )


def test_canonicalization_requires_declared_timezone_and_measurement_evidence(
    tmp_path: Path,
) -> None:
    manifest = _source(tmp_path)

    with pytest.raises(ValueError, match="canonicalization rules"):
        canonicalize_workbook(manifest)


def test_snapshot_preserves_rows_and_reports_invalid_source_rows(
    tmp_path: Path,
) -> None:
    manifest = _source(tmp_path)

    result = build_snapshot(manifest, tmp_path / "snapshot", _rules())

    assert len(result.events) == 3
    assert len({event["source_event_id"] for event in result.events}) == 3
    duplicate_time = [
        event
        for event in result.events
        if event["meter_id"] == "meter-a"
        and event["original_timestamp_text"] == "45292"
    ]
    assert len(duplicate_time) == 2
    assert {row["category"] for row in result.source_quality} == {
        "missing_numeric_value",
        "invalid_numeric_value",
    }
    unmatched = next(e for e in result.events if e["meter_id"] == "meter-b")
    assert unmatched["brick_entity_id"] is None
    assert unmatched["quality_flags"] == ["brick_unmatched"]
    matched = next(e for e in result.events if e["meter_id"] == "meter-a")
    assert matched["brick_building_ids"] == ["https://example.test/building-a"]
    assert matched["brick_zone_ids"] == ["https://example.test/zone-a"]
    assert matched["brick_metered_entities"] == [
        {
            "entity_id": "https://example.test/panel-a",
            "type_uris": ["https://brickschema.org/schema/Brick#Equipment"],
        }
    ]
    assert matched["brick_unit_uri"].endswith("KiloW-HR")
    assert matched["event_time_utc"].endswith("Z")
    assert matched["event_time_utc"].startswith("2023-12-31T16:00:00")
    assert matched["original_timestamp_text"] == "45292"
    assert matched["original_numeric_text"] == "10.00"


def test_snapshot_preserves_subsecond_source_precision_and_uses_sortable_utc(
    tmp_path: Path,
) -> None:
    manifest = _source(tmp_path)
    workbook_path = manifest._root / "readings.xlsx"
    workbook = load_workbook(workbook_path)
    workbook["Readings"]["A2"] = datetime(2024, 1, 1, 0, 0, 0, 500000)
    workbook.save(workbook_path)
    updated = register_dataset(
        manifest._root,
        tmp_path / "fractional-dataset-manifest.json",
        dataset_version="fixture-v1",
        source_variant="clean",
    )

    result = build_snapshot(updated, tmp_path / "snapshot", _rules())

    row = next(event for event in result.events if event["source_row_number"] == 2)
    assert row["original_timestamp_text"] == "45292.00000578703"
    assert row["event_time_utc"] == "2023-12-31T16:00:00.500000Z"


def test_ndjson_and_parquet_contain_the_same_sorted_exact_records(
    tmp_path: Path,
) -> None:
    manifest = _source(tmp_path)
    output = tmp_path / "snapshot"

    result = build_snapshot(manifest, output, _rules())

    ndjson_records = [
        json.loads(line)
        for line in (
            (output / "canonical.ndjson").read_text(encoding="utf-8").splitlines()
        )
    ]
    import pyarrow.parquet as pq

    parquet_records = pq.read_table(output / "canonical.parquet").to_pylist()
    assert ndjson_records == parquet_records == list(result.events)
    assert [row["source_event_id"] for row in ndjson_records] == sorted(
        row["source_event_id"] for row in ndjson_records
    )
    assert pq.read_schema(output / "canonical.parquet").field(
        "scaled_value"
    ).type == __import__("pyarrow").decimal128(38, 0)


def test_snapshot_manifest_binds_every_input_and_output_hash(tmp_path: Path) -> None:
    manifest = _source(tmp_path)
    output = tmp_path / "snapshot"

    result = build_snapshot(manifest, output, _rules())
    saved = json.loads((output / "snapshot-manifest.json").read_text("utf-8"))

    assert saved == result.manifest
    assert saved["status"] == "complete"
    assert saved["source_variant"] == "clean"
    assert saved["source_locator_fields"] == [
        "dataset_version",
        "source_variant",
        "source_relative_path",
        "workbook_sheet",
        "source_row_number",
    ]
    assert saved["artifacts"]["canonical_ndjson"]["sha256"] == _sha256(
        output / "canonical.ndjson"
    )
    assert saved["artifacts"]["canonical_parquet"]["sha256"] == _sha256(
        output / "canonical.parquet"
    )
    assert saved["brick"]["sha256"] == next(
        file.sha256 for file in manifest.files if file.media_kind == "brick_ttl"
    )
    assert saved["measurement_registry"]["meter-a"]["evidence"]
    assert saved["timezone"]["evidence"]
    assert saved["source_layout"]["sha256"] == _rules().source_layout.sha256()


def test_per_workbook_hkust_layout_derives_meter_from_registered_path(
    tmp_path: Path,
) -> None:
    root = tmp_path / "raw"
    source_dir = root / "Time-series data"
    source_dir.mkdir(parents=True)
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Sheet1"
    sheet.append(["time", "number"])
    sheet.append([datetime(2024, 1, 1, 0, 0), "10.10"])
    workbook.save(source_dir / "GUI.NO.D0001.xlsx")
    (root / "HKUST_Meter_Metadata.ttl").write_text(
        """\
@prefix brick: <https://brickschema.org/schema/Brick#> .
@prefix ref: <https://brickschema.org/schema/Brick/ref#> .
@prefix unit: <http://qudt.org/vocab/unit/> .
@prefix ex: <https://example.test/> .
ex:meter a brick:Electrical_Meter ;
  brick:hasUnit unit:KiloW-HR ;
  ref:hasExternalReference [ ref:hasTimeseriesId "D0001" ] .
""",
        encoding="utf-8",
    )
    manifest = register_dataset(
        root,
        tmp_path / "manifest.json",
        dataset_version="dryad-v5",
        source_variant="raw",
    )
    evidence = "synthetic representation of the authors' documented source layout"
    rules = CanonicalizationRules(
        source_timezone="Asia/Hong_Kong",
        timezone_evidence=evidence,
        source_layout=SourceLayoutRules(
            rules=(
                WorkbookLayoutRule(
                    name="hkust-raw-per-meter",
                    relative_path_pattern=(
                        r"Time-series data/GUI\.NO\.(?P<meter_id>[A-Z][0-9]{4})"
                        r"\.xlsx"
                    ),
                    sheet_name="Sheet1",
                    header_row=1,
                    expected_columns=("time", "number"),
                    timestamp_column="time",
                    value_column="number",
                    meter_id_path_group="meter_id",
                    evidence=evidence,
                ),
            ),
            evidence=evidence,
        ),
        measurements={
            "D0001": MeasurementRule(
                "cumulative_energy", "kWh", 2, evidence, "KiloW-HR"
            )
        },
    )

    result = build_snapshot(manifest, tmp_path / "snapshot", rules)

    assert len(result.events) == 1
    assert result.events[0]["meter_id"] == "D0001"
    assert result.events[0]["source_relative_path"] == (
        "Time-series data/GUI.NO.D0001.xlsx"
    )


def test_unexpected_sheet_or_header_is_rejected_by_layout(tmp_path: Path) -> None:
    manifest = _source(tmp_path)
    rules = _rules()
    source = manifest._root / "readings.xlsx"  # type: ignore[operator]
    workbook = __import__("openpyxl").load_workbook(source)
    workbook.create_sheet("Undeclared")
    workbook.save(source)
    changed = register_dataset(
        manifest._root,  # type: ignore[arg-type]
        tmp_path / "changed-manifest.json",
        dataset_version="fixture-v1",
        source_variant="clean",
    )

    with pytest.raises(ValueError, match="unexpected workbook sheets"):
        build_snapshot(changed, tmp_path / "snapshot", rules)


def test_snapshot_is_immutable_and_reproducible_across_directories(
    tmp_path: Path,
) -> None:
    manifest = _source(tmp_path)
    first = tmp_path / "snapshot-a"
    second = tmp_path / "snapshot-b"

    build_snapshot(manifest, first, _rules())
    build_snapshot(manifest, second, _rules())

    for name in (
        "canonical.ndjson",
        "canonical.parquet",
        "source-quality.ndjson",
        "snapshot-manifest.json",
    ):
        assert (first / name).read_bytes() == (second / name).read_bytes()
    with pytest.raises(FileExistsError, match="immutable snapshot"):
        build_snapshot(manifest, first, _rules())


def test_contract_mismatch_between_brick_unit_and_rule_fails(tmp_path: Path) -> None:
    manifest = _source(tmp_path)
    bad_rule = _rules().with_measurement(
        "meter-a",
        MeasurementRule(
            "cumulative_energy", "kWh", 2, "synthetic fixture declaration", "W"
        ),
    )

    with pytest.raises(ValueError, match="Brick unit contract mismatch"):
        build_snapshot(manifest, tmp_path / "snapshot", bad_rule)


def test_required_brick_unit_rejects_an_unmatched_meter(tmp_path: Path) -> None:
    manifest = _source(tmp_path)
    rules = _rules().with_measurement(
        "meter-b",
        MeasurementRule(
            "cumulative_energy",
            "kWh",
            2,
            "synthetic fixture declaration",
            "KiloW-HR",
        ),
    )

    with pytest.raises(ValueError, match="Brick unit contract mismatch"):
        build_snapshot(manifest, tmp_path / "snapshot", rules)
