"""Read registered workbook rows through an exact source-layout contract.

Memory is incremental, with per-workbook openpyxl overhead, not strictly O(1)
in workbook size. openpyxl caches shared strings/styles and its worksheet parser
retains cleared row elements. The additional lexical stream detaches completed
rows and retains only row text plus XML read-ahead. No dataset-wide row list is
built here; callers must consume the iterator incrementally. This suits the
individually limited HKUST workbooks; arbitrary large workbooks or shared-string
tables can still require substantial memory through openpyxl.
"""

from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Generator, Iterator
from xml.etree.ElementTree import iterparse
from zipfile import ZipFile

from .identity import SourceLocator
from .manifests import DatasetManifest
from .source_layout import SourceLayoutRules, WorkbookLayoutRule

if TYPE_CHECKING:
    from openpyxl.worksheet.worksheet import Worksheet


@dataclass(frozen=True)
class WorkbookSourceRow:
    """One physical source row before semantic conversion."""

    locator: SourceLocator
    layout_rule: WorkbookLayoutRule
    timestamp_value: object
    meter_id_value: object
    numeric_value: object
    row_values: tuple[Any, ...]
    # Numeric/date/boolean/error/cached-formula <v> text, without float conversion.
    # Strings retain decoded cell text (not shared-string indexes or XML markup).
    # Missing cells and formulas without a cached value have no source text.
    timestamp_text: str | None = None
    numeric_text: str | None = None


@dataclass(frozen=True)
class WorkbookSourceStart:
    """Validated workbook boundary, emitted even when it has no data rows."""

    relative_path: str
    sheet_name: str
    layout_rule: WorkbookLayoutRule
    path_meter_id: str | None


def _iter_worksheet_text(
    path: Path, worksheet_path: str
) -> Generator[tuple[int, dict[int, str]], None, None]:
    """Stream stored <v> text, retaining at most one worksheet row.

    openpyxl remains responsible for inline/shared-string decoding, styles and
    date epochs. Boolean text is provenance only; consumers must gate parsed types.
    Formula text is not evaluated; only its cached result, if any, is a value.
    """
    from openpyxl.utils.cell import coordinate_to_tuple

    ns = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
    with ZipFile(path) as archive, archive.open(worksheet_path) as stream:
        sheet_data = None
        previous_row = 0
        for event, element in iterparse(stream, events=("start", "end")):
            if event == "start" and element.tag == ns + "sheetData":
                sheet_data = element
            if event != "end" or element.tag != ns + "row":
                continue
            physical_row = int(element.get("r", str(previous_row + 1)))
            previous_row = physical_row
            texts = {}
            column = 0
            for cell in element:
                if cell.tag != ns + "c":
                    continue
                coordinate = cell.get("r")
                column = (
                    coordinate_to_tuple(coordinate)[1] if coordinate else column + 1
                )
                if cell.get("t", "n") not in {"n", "d", "str", "e", "b"}:
                    continue
                value = cell.find(ns + "v")
                if value is not None and value.text is not None:
                    # Cells may omit coordinates; XLSX then implies column order.
                    texts[column] = value.text
            if sheet_data is not None:
                sheet_data.remove(element)
            element.clear()
            yield physical_row, texts


def _cell_text(value: object, stored: str | None) -> str | None:
    if stored is not None:
        return stored
    return value if isinstance(value, str) else None


def _validated_data_sheet(
    workbook: Any,
    relative_path: str,
    layout: WorkbookLayoutRule,
) -> tuple["Worksheet", dict[str, int]]:
    actual_sheets = tuple(sheet.title for sheet in workbook.worksheets)
    declared_sheets = (layout.sheet_name, *layout.ignored_sheet_names)
    if set(actual_sheets) != set(declared_sheets) or len(actual_sheets) != len(
        declared_sheets
    ):
        raise ValueError(
            f"unexpected workbook sheets in {relative_path}: "
            f"expected {list(declared_sheets)!r}, got {list(actual_sheets)!r}"
        )
    worksheet = workbook[layout.sheet_name]
    rows = worksheet.iter_rows(min_row=layout.header_row, values_only=True)
    try:
        header_values = next(rows)
    except StopIteration as exc:
        raise ValueError(
            f"missing declared header row in {relative_path}:{worksheet.title}"
        ) from exc
    headers = tuple(
        "" if value is None else str(value).strip() for value in header_values
    )
    if headers != layout.expected_columns:
        raise ValueError(
            f"source-layout header mismatch in {relative_path}:{worksheet.title}: "
            f"expected {list(layout.expected_columns)!r}, got {list(headers)!r}"
        )
    return worksheet, {header: index for index, header in enumerate(headers)}


def iter_workbook_source_items(
    manifest: DatasetManifest,
    source_layout: SourceLayoutRules,
) -> Iterator[WorkbookSourceStart | WorkbookSourceRow]:
    """Yield each validated workbook boundary followed by its physical rows."""

    try:
        from openpyxl import load_workbook
    except ImportError as exc:  # pragma: no cover - dependency gate
        raise RuntimeError("dataset extra is required for workbooks") from exc

    if manifest._root is None:
        raise ValueError("manifest must retain a verified source root")
    manifest._validate_files(manifest._root)

    for file_manifest in manifest.files:
        if file_manifest.media_kind != "workbook":
            continue
        resolved = source_layout.resolve(file_manifest.relative_path)
        workbook_path = manifest._root / file_manifest.relative_path
        workbook = load_workbook(
            workbook_path,
            read_only=True,
            data_only=True,
        )
        try:
            worksheet, lookup = _validated_data_sheet(
                workbook,
                file_manifest.relative_path,
                resolved.rule,
            )
            yield WorkbookSourceStart(
                relative_path=file_manifest.relative_path,
                sheet_name=worksheet.title,
                layout_rule=resolved.rule,
                path_meter_id=resolved.path_meter_id,
            )
            rows = worksheet.iter_rows(
                min_row=resolved.rule.header_row + 1,
                values_only=True,
            )
            # ReadOnlyWorksheet's resolved package path follows workbook relations;
            # sheet titles and positions need not match worksheet member names.
            with closing(
                _iter_worksheet_text(workbook_path, worksheet._worksheet_path)
            ) as raw_rows:
                pending = next(raw_rows, None)
                for physical_row, row in enumerate(
                    rows, start=resolved.rule.header_row + 1
                ):
                    while pending is not None and pending[0] < physical_row:
                        pending = next(raw_rows, None)
                    texts = pending[1] if pending and pending[0] == physical_row else {}
                    timestamp_index = lookup[resolved.rule.timestamp_column]
                    numeric_index = lookup[resolved.rule.value_column]
                    meter_id = (
                        resolved.path_meter_id
                        if resolved.path_meter_id is not None
                        else row[lookup[resolved.rule.meter_id_column]]  # type: ignore[index]
                    )
                    yield WorkbookSourceRow(
                        locator=SourceLocator(
                            manifest.dataset_version,
                            manifest.source_variant,
                            file_manifest.relative_path,
                            worksheet.title,
                            physical_row,
                        ),
                        layout_rule=resolved.rule,
                        timestamp_value=row[timestamp_index],
                        meter_id_value=meter_id,
                        numeric_value=row[numeric_index],
                        row_values=tuple(row),
                        timestamp_text=_cell_text(
                            row[timestamp_index],
                            texts.get(timestamp_index + 1),
                        ),
                        numeric_text=_cell_text(
                            row[numeric_index],
                            texts.get(numeric_index + 1),
                        ),
                    )
        finally:
            workbook.close()


def iter_workbook_source_rows(
    manifest: DatasetManifest,
    source_layout: SourceLayoutRules,
) -> Iterator[WorkbookSourceRow]:
    """Yield every declared physical data row in manifest path order."""

    for item in iter_workbook_source_items(manifest, source_layout):
        if isinstance(item, WorkbookSourceRow):
            yield item
