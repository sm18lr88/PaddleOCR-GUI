"""excel_to_json and excel_to_csv: workbook sheets as JSON or RFC 4180 CSV."""

import csv
import datetime as dt
import json
import math
import shutil
from collections.abc import Iterable
from pathlib import Path
from typing import Annotated, Final

from openpyxl import Workbook
from openpyxl.worksheet.worksheet import Worksheet
from pydantic import Field, JsonValue

from paddlepdf.pdftools.common import input_path, output_path
from paddlepdf.pdftools.contract import PdfToolError, ToolOutcome
from paddlepdf.pdftools.office.formats import (
    cell_text,
    open_xlsx,
    sheet_rows,
    worksheets,
)

EXCEL_SUFFIXES: Final = (".xlsx", ".xlsm", ".xltx", ".xltm", ".xls")


def _json_value(value: object) -> JsonValue:
    if value is None or isinstance(value, bool | int | str):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else 0
    if isinstance(value, dt.datetime | dt.date | dt.time):
        return value.isoformat()
    return str(value)


def _select(workbook: Workbook, sheet: str | None) -> list[Worksheet]:
    sheets = worksheets(workbook)
    if sheet is None:
        return sheets
    chosen = [candidate for candidate in sheets if candidate.title == sheet]
    if not chosen:
        names = ", ".join(candidate.title for candidate in sheets)
        msg = f"Sheet not found: {sheet} (available: {names})"
        raise PdfToolError(msg)
    return chosen


def _record(row: Iterable[object], columns: list[JsonValue]) -> JsonValue:
    record: dict[str, JsonValue] = {}
    for index, value in enumerate(row):
        key = str(columns[index]) if index < len(columns) else f"Column{index}"
        record[key] = _json_value(value)
    return record


def _sheet_json(sheet: Worksheet, *, has_headers: bool) -> dict[str, JsonValue]:
    rows = sheet_rows(sheet)
    columns: list[JsonValue] = []
    body = rows
    if has_headers and rows:
        columns = [
            cell_text(value) if value is not None else f"Column{index}"
            for index, value in enumerate(rows[0])
        ]
        body = rows[1:]
    data: list[JsonValue] = [
        _record(row, columns) if has_headers else [_json_value(value) for value in row]
        for row in body
    ]
    return {
        "name": sheet.title,
        "rows_count": len(rows),
        "columns": columns,
        "data": data,
    }


def excel_to_json(
    input_file: Annotated[str, Field(description="Excel workbook (.xlsx/.xlsm).")],
    output_file: Annotated[
        str | None, Field(description="Optional .json path to also save the result.")
    ] = None,
    sheet: Annotated[
        str | None, Field(description="Only this sheet name; default every sheet.")
    ] = None,
    *,
    has_headers: Annotated[
        bool, Field(description="Treat the first row as column names (row objects).")
    ] = True,
) -> ToolOutcome:
    source = input_path(input_file, EXCEL_SUFFIXES)
    workbook = open_xlsx(source)
    sheets = [
        _sheet_json(item, has_headers=has_headers) for item in _select(workbook, sheet)
    ]
    workbook.close()
    result: dict[str, JsonValue] = {"sheets": list[JsonValue](sheets)}
    if output_file is None:
        return ToolOutcome(data=result)
    target = output_path(output_file, source)
    target.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    return ToolOutcome(output_files=(str(target),), data=result)


def _write_csv(sheet: Worksheet, target: Path) -> int:
    rows = sheet_rows(sheet)
    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerows([cell_text(value) for value in row] for row in rows)
    return len(rows)


def _safe_name(title: str) -> str:
    return "".join(char if char.isalnum() or char in "-_" else "_" for char in title)


def excel_to_csv(
    input_file: Annotated[str, Field(description="Excel workbook (.xlsx/.xlsm).")],
    output_file: Annotated[str, Field(description="Destination .csv path.")],
    sheet: Annotated[
        str | None,
        Field(description="Sheet to export; default exports every sheet."),
    ] = None,
) -> ToolOutcome:
    source = input_path(input_file, EXCEL_SUFFIXES)
    target = output_path(output_file, source)
    workbook = open_xlsx(source)
    sheets = _select(workbook, sheet)
    if not sheets:
        msg = f"No worksheets found in {source}"
        raise PdfToolError(msg)
    written: list[str] = []
    exported: list[JsonValue] = []
    if len(sheets) == 1:
        rows = _write_csv(sheets[0], target)
        written.append(str(target))
        exported.append({"sheet": sheets[0].title, "rows": rows, "file": str(target)})
    else:
        suffix = target.suffix or ".csv"
        for index, item in enumerate(sheets):
            dest = target.with_name(f"{target.stem}_{_safe_name(item.title)}{suffix}")
            rows = _write_csv(item, dest)
            if index == 0 and dest != target:
                shutil.copyfile(dest, target)
                written.append(str(target))
            written.append(str(dest))
            exported.append({"sheet": item.title, "rows": rows, "file": str(dest)})
    workbook.close()
    return ToolOutcome(output_files=tuple(written), data={"sheets": exported})
