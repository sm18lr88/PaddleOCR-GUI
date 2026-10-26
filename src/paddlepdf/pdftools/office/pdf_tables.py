"""pdf_to_xlsx: PaperPilot table.rs row/column clustering over located page words.

pdfium page text collapses column gaps to single spaces, so words are located with
whole-word searches on a one-page copy of each page to recover their x/y boxes.
"""

import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Final, cast

import pikepdf
from openpyxl import Workbook
from pydantic import Field, JsonValue

from paddlepdf.pdftools.common import input_path, open_pdf, output_path
from paddlepdf.pdftools.contract import ToolOutcome
from paddlepdf.pdftools.office.formats import page_lines
from paddlepdf.pdftools.pdfium import find_text_boxes, page_texts

if TYPE_CHECKING:
    from openpyxl.worksheet.worksheet import Worksheet

_ROW_TOLERANCE: Final = 8.0
_COLUMN_SLACK: Final = 5.0
_NEST_SLACK: Final = 0.5
_MIN_TABLE_SPAN: Final = 2


@dataclass(frozen=True, slots=True)
class Word:
    text: str
    left: float
    bottom: float
    right: float


def _contained(inner: Word, outer: Word) -> bool:
    return (
        len(outer.text) > len(inner.text)
        and outer.left - _NEST_SLACK <= inner.left
        and inner.right <= outer.right + _NEST_SLACK
        and abs(outer.bottom - inner.bottom) <= 1.0
    )


def locate_words(page_pdf: Path, text: str) -> list[Word]:
    """Box every whitespace token of ``text``; drop hits nested in a longer token."""
    words: list[Word] = []
    for token in sorted(set(text.split())):
        boxes = find_text_boxes(page_pdf, token, match_case=True, whole_word=True)
        words.extend(
            Word(token, left, bottom, right)
            for left, bottom, right, _top in boxes.get(0, [])
        )
    return [word for word in words if not any(_contained(word, o) for o in words)]


def _rows(words: list[Word]) -> list[list[Word]]:
    ordered = sorted(words, key=lambda word: (-word.bottom, word.left))
    rows: list[list[Word]] = []
    current_y = ordered[0].bottom
    current: list[Word] = []
    for word in ordered:
        if abs(word.bottom - current_y) <= _ROW_TOLERANCE:
            current.append(word)
        else:
            rows.append(current)
            current = [word]
            current_y = word.bottom
    rows.append(current)
    return [sorted(row, key=lambda word: word.left) for row in rows]


def _columns(rows: list[list[Word]]) -> list[tuple[float, float]]:
    intervals: list[list[float]] = []
    for word in (word for row in rows for word in row):
        for interval in intervals:
            if (
                word.left <= interval[1] + _COLUMN_SLACK
                and word.right + _COLUMN_SLACK >= interval[0]
            ):
                interval[0] = min(interval[0], word.left)
                interval[1] = max(interval[1], word.right)
                break
        else:
            intervals.append([word.left, word.right])
    merged: list[tuple[float, float]] = []
    for start, end in sorted(intervals):
        if merged and start <= merged[-1][1] + _COLUMN_SLACK:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def table_grid(words: list[Word]) -> list[list[str]] | None:
    """Return the table.rs grid, or None when the page has <2 rows or <2 columns."""
    if not words:
        return None
    rows = _rows(words)
    columns = _columns(rows)
    if len(rows) < _MIN_TABLE_SPAN or len(columns) < _MIN_TABLE_SPAN:
        return None
    grid: list[list[str]] = []
    for row in rows:
        cells = [""] * len(columns)
        for word in row:
            middle = (word.left + word.right) / 2
            for index, (start, end) in enumerate(columns):
                if start - _COLUMN_SLACK <= middle <= end + _COLUMN_SLACK:
                    cells[index] = f"{cells[index]} {word.text}".strip()
                    break
        grid.append(cells)
    return grid


def _page_grids(
    source: Path, password: str | None, texts: list[str]
) -> list[list[list[str]] | None]:
    grids: list[list[list[str]] | None] = []
    with open_pdf(source, password) as pdf, tempfile.TemporaryDirectory() as scratch:
        for index, page in enumerate(pdf.pages):
            single_path = Path(scratch) / f"page-{index + 1}.pdf"
            with pikepdf.new() as single:
                single.pages.append(page)
                single.save(single_path)
            grids.append(table_grid(locate_words(single_path, texts[index])))
    return grids


def pdf_to_xlsx(
    input_file: Annotated[str, Field(description="Source PDF.")],
    output_file: Annotated[str, Field(description="Destination .xlsx path.")],
    password: Annotated[
        str | None, Field(description="Password for an encrypted input PDF.")
    ] = None,
) -> ToolOutcome:
    source = input_path(input_file)
    target = output_path(output_file, source)
    texts = page_texts(source, password)
    grids = _page_grids(source, password, texts)
    workbook = Workbook()
    default = workbook.active
    if default is not None:
        workbook.remove(default)
    pages: list[JsonValue] = []
    for number, (text, grid) in enumerate(zip(texts, grids, strict=True), start=1):
        sheet = cast("Worksheet", workbook.create_sheet(f"Page {number}"))
        rows = grid if grid is not None else [[line] for line in page_lines(text)]
        for row in rows:
            sheet.append(row)
        pages.append(
            {
                "page": number,
                "table_detected": grid is not None,
                "rows": len(rows),
                "columns": max((len(row) for row in rows), default=0),
            }
        )
    workbook.save(target)
    return ToolOutcome(output_files=(str(target),), data={"pages": pages})
