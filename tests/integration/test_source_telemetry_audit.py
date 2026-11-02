from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile

import pytest
from openpyxl import Workbook, load_workbook

from iot_energy_pipeline.manifests import register_dataset
from iot_energy_pipeline.source_audit import audit_source_telemetry
from iot_energy_pipeline.source_layout import (
    SourceLayoutRules,
    WorkbookLayoutRule,
)
from iot_energy_pipeline.workbook_source import iter_workbook_source_rows


@pytest.mark.parametrize(
    ("cell_xml", "text", "parsed"),
    [
        ('<c r="B2"><v>1.2300E-3</v></c>', "1.2300E-3", 0.00123),
        (
            '<c r="B2"><f>1/3</f><v>0.333333333333333333</v></c>',
            "0.333333333333333333",
            1 / 3,
        ),
        ('<c r="B2"><f>1/3</f><v/></c>', None, None),
        (
            '<c r="B2" t="inlineStr"><is><r><t> 1.</t></r><r><t>2300 </t></r></is></c>',
            " 1.2300 ",
            " 1.2300 ",
        ),
        ('<c r="B2" t="s"><v>0</v></c>', " 1.2300 ", " 1.2300 "),
        ('<c r="B2" t="str"><f>"1.23"</f><v> 1.2300 </v></c>', " 1.2300 ", " 1.2300 "),
        ('<c r="B2" t="b"><v>1</v></c>', "1", True),
        ('<c r="B2" t="b"><v>0</v></c>', "0", False),
        ('<c r="B2" t="b"><f>1=1</f><v>1</v></c>', "1", True),
        ('<c r="B2" t="e"><v>#DIV/0!</v></c>', "#DIV/0!", "#DIV/0!"),
        ("<c><v>1.000000000000000001</v></c>", "1.000000000000000001", 1.0),
    ],
)
def test_source_text_defines_cached_formulas_and_decoded_strings(
    tmp_path: Path, cell_xml: str, text: str | None, parsed: object
) -> None:
    manifest, layout = _source(tmp_path)
    path = manifest._root / "Time-series data/GUI.NO.D0001.xlsx"
    with ZipFile(path) as archive:
        entries = {name: archive.read(name) for name in archive.namelist()}
    ns_uri = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    ns = "{" + ns_uri + "}"
    sheet = ET.fromstring(entries["xl/worksheets/sheet1.xml"])
    row = sheet.find(f".//{ns}row[@r='2']")
    row.remove(row.find(f"{ns}c[@r='B2']"))
    row.append(ET.fromstring(cell_xml.replace("<c", f'<c xmlns="{ns_uri}"', 1)))
    # A missing physical row must not shift raw text onto another parsed row.
    data = sheet.find(ns + "sheetData")
    data.remove(data.find(f"{ns}row[@r='3']"))
    entries["xl/worksheets/sheet1.xml"] = ET.tostring(sheet)
    entries["xl/sharedStrings.xml"] = (
        f'<sst xmlns="{ns_uri}"><si><t xml:space="preserve"> 1.2300 </t></si></sst>'
    ).encode()
    types = ET.fromstring(entries["[Content_Types].xml"])
    ET.SubElement(
        types,
        "{http://schemas.openxmlformats.org/package/2006/content-types}Override",
        {
            "PartName": "/xl/sharedStrings.xml",
            "ContentType": (
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sharedStrings+xml"
            ),
        },
    )
    entries["[Content_Types].xml"] = ET.tostring(types)
    # Follow the workbook relationship rather than guessing a sheet1.xml member.
    entries["xl/worksheets/readings.xml"] = entries.pop("xl/worksheets/sheet1.xml")
    entries["xl/_rels/workbook.xml.rels"] = entries[
        "xl/_rels/workbook.xml.rels"
    ].replace(b"/xl/worksheets/sheet1.xml", b"/xl/worksheets/readings.xml")
    with ZipFile(path, "w") as archive:
        for name, content in entries.items():
            archive.writestr(name, content)
    manifest = register_dataset(
        manifest._root,
        tmp_path / "xml-manifest.json",
        dataset_version="fixture",
        source_variant="raw",
    )

    rows = list(iter_workbook_source_rows(manifest, layout))

    assert rows[0].numeric_text == text
    assert rows[0].numeric_value == parsed
    assert rows[1].locator.physical_row == 3
    assert rows[1].numeric_value is None
    assert rows[1].numeric_text is None
    assert rows[2].numeric_text == "11.50"


@pytest.mark.parametrize("value", [False, True])
def test_audit_rejects_parsed_booleans_despite_numeric_lexical_text(
    tmp_path: Path, value: bool
) -> None:
    manifest, layout = _source(tmp_path)
    path = manifest._root / "Time-series data/GUI.NO.D0001.xlsx"
    workbook = load_workbook(path)
    workbook["Sheet1"]["A2"] = value
    workbook["Sheet1"]["B2"] = value
    workbook.save(path)
    manifest = register_dataset(
        manifest._root,
        tmp_path / "boolean-manifest.json",
        dataset_version="fixture",
        source_variant="raw",
    )

    row = next(iter_workbook_source_rows(manifest, layout))
    report = audit_source_telemetry(manifest, layout, tmp_path / "audit.json")

    assert row.timestamp_text == row.numeric_text == str(int(value))
    assert row.timestamp_value is row.numeric_value is value
    assert report["totals"]["invalid_numeric_count"] == 2
    assert report["totals"]["invalid_timestamp_count"] == 2
    assert report["totals"]["finite_numeric_count"] == 5
    assert report["totals"]["zero_numeric_count"] == 1
    assert report["workbooks"][0]["decimal_scale_histogram"] == {"2": 5}


@pytest.mark.parametrize(
    ("iso_dates", "mac_epoch"), [(False, False), (False, True), (True, False)]
)
def test_source_timestamp_keeps_stored_text_and_parses_workbook_epoch(
    tmp_path: Path, iso_dates: bool, mac_epoch: bool
) -> None:
    from openpyxl.utils.datetime import CALENDAR_MAC_1904

    manifest, layout = _source(tmp_path)
    path = manifest._root / "Time-series data/GUI.NO.D0001.xlsx"
    workbook = load_workbook(path)
    workbook.iso_dates = iso_dates
    if mac_epoch:
        workbook.epoch = CALENDAR_MAC_1904
    workbook.save(path)
    manifest = register_dataset(
        manifest._root,
        tmp_path / "epoch-manifest.json",
        dataset_version="fixture",
        source_variant="raw",
    )

    row = next(iter_workbook_source_rows(manifest, layout))

    assert row.timestamp_value == datetime(2024, 1, 1)
    assert row.timestamp_text == (
        "2024-01-01T00:00:00" if iso_dates else "43830" if mac_epoch else "45292"
    )


def test_source_rows_and_audit_retain_numeric_xml_precision(tmp_path: Path) -> None:
    manifest, layout = _source(tmp_path)
    path = manifest._root / "Time-series data/GUI.NO.D0001.xlsx"
    with ZipFile(path) as archive:
        entries = {name: archive.read(name) for name in archive.namelist()}
    ns = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
    sheet = ET.fromstring(entries["xl/worksheets/sheet1.xml"])
    for coordinate, text in (
        ("B2", "1.000000000000000002"),
        ("B3", "1.000000000000000001"),
    ):
        cell = sheet.find(f".//{ns}c[@r='{coordinate}']")
        cell.clear()
        cell.attrib.update(r=coordinate, t="n")
        ET.SubElement(cell, ns + "v").text = text
    entries["xl/worksheets/sheet1.xml"] = ET.tostring(sheet)
    with ZipFile(path, "w") as archive:
        for name, data in entries.items():
            archive.writestr(name, data)
    manifest = register_dataset(
        manifest._root,
        tmp_path / "xml-manifest.json",
        dataset_version="fixture",
        source_variant="raw",
    )

    report = audit_source_telemetry(manifest, layout, tmp_path / "audit.json")

    assert report["workbooks"][0]["decimal_scale_histogram"] == {"2": 4, "18": 2}
    assert report["totals"]["ordered_numeric_decrease_count"] == 3
    rows = list(iter_workbook_source_rows(manifest, layout))
    assert rows[0].numeric_text == "1.000000000000000002"
    assert rows[0].timestamp_text == "45292"
    assert rows[0].timestamp_value == datetime(2024, 1, 1)
    assert rows[0].numeric_value == 1.0
    assert rows[5].locator.physical_row == 7
    assert rows[5].numeric_text is None


def _source(tmp_path: Path):
    root = tmp_path / "raw"
    source = root / "Time-series data"
    source.mkdir(parents=True)
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Sheet1"
    sheet.append(["time", "number"])
    sheet.append([datetime(2024, 1, 1, 0, 0), "10.00"])
    sheet.append([datetime(2024, 1, 1, 0, 15), "11.00"])
    sheet.append([datetime(2024, 1, 1, 0, 15), "11.50"])
    sheet.append([datetime(2024, 1, 1, 0, 45), "NaN"])
    sheet.append([datetime(2024, 1, 1, 0, 30), "9.00"])
    sheet.append([None, None])
    sheet.append(["bad-time", "bad-number"])
    sheet.append([datetime(2024, 1, 1, 1, 0), "0.00"])
    sheet.append([datetime(2024, 1, 1, 1, 15), "-1.00"])
    workbook.save(source / "GUI.NO.D0001.xlsx")
    manifest = register_dataset(
        root,
        tmp_path / "manifest.json",
        dataset_version="dryad-v5-test",
        source_variant="raw",
    )
    evidence = "synthetic source-layout test based on the authors' public code"
    layout = SourceLayoutRules(
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
    )
    return manifest, layout


def test_audit_reports_exact_source_quality_without_assigning_semantics(
    tmp_path: Path,
) -> None:
    manifest, layout = _source(tmp_path)

    report = audit_source_telemetry(manifest, layout, tmp_path / "audit.json")

    assert report["schema_version"] == "source-telemetry-audit-v1"
    assert report["source_variant"] == "raw"
    assert report["timezone_assignment"] == "UNASSIGNED"
    assert report["measurement_semantics_assignment"] == "UNASSIGNED"
    assert report["totals"] == {
        "workbook_count": 1,
        "empty_workbook_count": 0,
        "meter_count": 1,
        "source_row_count": 9,
        "empty_source_row_count": 1,
        "missing_meter_id_count": 0,
        "missing_timestamp_count": 1,
        "invalid_timestamp_count": 1,
        "naive_timestamp_count": 7,
        "aware_timestamp_count": 0,
        "duplicate_timestamp_count": 1,
        "out_of_order_timestamp_count": 1,
        "missing_numeric_count": 1,
        "invalid_numeric_count": 1,
        "non_finite_numeric_count": 1,
        "finite_numeric_count": 6,
        "zero_numeric_count": 1,
        "negative_numeric_count": 1,
        "ordered_numeric_decrease_count": 3,
    }
    workbook = report["workbooks"][0]
    assert workbook["relative_path"] == "Time-series data/GUI.NO.D0001.xlsx"
    assert workbook["empty_workbook"] is False
    assert workbook["meter_ids"] == ["D0001"]
    assert workbook["cadence_seconds_histogram"] == {"900": 5}
    assert workbook["decimal_scale_histogram"] == {"2": 6}
    assert workbook["timestamp_bounds"] == {
        "naive": {
            "minimum": "2024-01-01T00:00:00",
            "maximum": "2024-01-01T01:15:00",
        },
        "aware_utc": {"minimum": None, "maximum": None},
    }


def test_audit_json_is_byte_reproducible_and_binds_layout(tmp_path: Path) -> None:
    manifest, layout = _source(tmp_path)
    first = tmp_path / "audit-a.json"
    second = tmp_path / "audit-b.json"

    report = audit_source_telemetry(manifest, layout, first)
    audit_source_telemetry(manifest, layout, second)

    assert first.read_bytes() == second.read_bytes()
    assert json.loads(first.read_text(encoding="utf-8")) == report
    assert report["source_layout_sha256"] == layout.sha256()
    assert report["dataset_manifest_sha256"]


def test_source_audit_is_available_through_the_cli(tmp_path: Path) -> None:
    manifest, layout = _source(tmp_path)
    manifest_path = tmp_path / "manifest.json"
    layout_path = tmp_path / "layout.json"
    output = tmp_path / "cli-audit.json"
    layout.to_json(layout_path)
    from iot_energy_pipeline.cli import main

    result = main(
        [
            "audit-source",
            "--manifest",
            str(manifest_path),
            "--root",
            str(manifest._root),
            "--layout",
            str(layout_path),
            "--output",
            str(output),
        ]
    )

    assert result == 0
    assert output.exists()


def test_valid_header_only_workbook_is_reported_as_empty(tmp_path: Path) -> None:
    manifest, layout = _source(tmp_path)
    empty = Workbook()
    sheet = empty.active
    sheet.title = "Sheet1"
    sheet.append(["time", "number"])
    empty.save(manifest._root / "Time-series data" / "GUI.NO.D0002.xlsx")
    updated = register_dataset(
        manifest._root,
        tmp_path / "updated-manifest.json",
        dataset_version="dryad-v5-test",
        source_variant="raw",
    )

    report = audit_source_telemetry(updated, layout, tmp_path / "audit.json")

    assert report["totals"]["workbook_count"] == 2
    assert report["totals"]["empty_workbook_count"] == 1
    empty_report = next(
        workbook
        for workbook in report["workbooks"]
        if workbook["relative_path"].endswith("D0002.xlsx")
    )
    assert empty_report["empty_workbook"] is True
    assert empty_report["source_row_count"] == 0
    assert empty_report["meter_ids"] == ["D0002"]


def test_source_audit_preserves_subsecond_timestamp_bounds(tmp_path: Path) -> None:
    manifest, layout = _source(tmp_path)
    workbook_path = manifest._root / "Time-series data" / "GUI.NO.D0001.xlsx"
    workbook = load_workbook(workbook_path)
    workbook["Sheet1"]["A2"] = datetime(2024, 1, 1, 0, 0, 0, 500000)
    workbook.save(workbook_path)
    updated = register_dataset(
        manifest._root,
        tmp_path / "fractional-manifest.json",
        dataset_version="dryad-v5-test",
        source_variant="raw",
    )

    report = audit_source_telemetry(updated, layout, tmp_path / "audit.json")

    assert report["workbooks"][0]["timestamp_bounds"]["naive"]["minimum"] == (
        "2024-01-01T00:00:00.500000"
    )
