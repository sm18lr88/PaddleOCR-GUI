"""pdf_booklet: reorder pages into booklet order, optionally as 2-up sheets."""

from itertools import batched
from typing import Annotated

import pikepdf
from pydantic import Field, JsonValue

from paddlepdf.pdftools.common import input_path, open_pdf, output_path, save_pdf
from paddlepdf.pdftools.contract import PdfToolError, ToolOutcome
from paddlepdf.pdftools.layout.compose import (
    PageForm,
    Placement,
    add_sheet,
    import_page,
    page_size,
)


def booklet_sequence(page_count: int) -> list[int]:
    """1-based page order for folding; numbers above ``page_count`` are blank pads."""
    total = page_count + (-page_count % 4)
    sequence: list[int] = []
    for sheet in range(total // 4):
        sequence += [
            total - 2 * sheet,
            2 * sheet + 1,
            2 * sheet + 2,
            total - 2 * sheet - 1,
        ]
    return sequence


def pdf_booklet(
    input_file: Annotated[str, Field(description="Path to the source PDF.")],
    output_file: Annotated[str, Field(description="Path of the booklet PDF to write.")],
    create_sheets: Annotated[
        bool,
        Field(
            description="True: one 2-up sheet per spread; False: only reorder pages."
        ),
    ] = True,
    center_fold_line: Annotated[
        bool,
        Field(description="Draw a dashed fold line down the middle of each sheet."),
    ] = False,
    gutter_pt: Annotated[
        float,
        Field(ge=0, description="Gap in points between the two pages of a sheet."),
    ] = 0.0,
    password: Annotated[
        str | None, Field(description="Password if the input is encrypted.")
    ] = None,
) -> ToolOutcome:
    source_path = input_path(input_file)
    target = output_path(output_file, source_path)
    source = open_pdf(source_path, password)
    count = len(source.pages)
    if count == 0:
        msg = "Document contains no pages"
        raise PdfToolError(msg)
    sequence = booklet_sequence(count)
    blank_size = page_size(source.pages[0])
    out = pikepdf.new()
    if create_sheets:
        _impose(out, source, sequence, blank_size, gutter_pt, center_fold_line)
    else:
        for number in sequence:
            if number <= count:
                out.pages.append(source.pages[number - 1])
            else:
                out.add_blank_page(page_size=blank_size)
    written = save_pdf(out, target)
    pad_sequence: list[JsonValue] = [*sequence]
    data: dict[str, JsonValue] = {
        "source_pages": count,
        "padded_pages": len(sequence) - count,
        "output_pages": len(out.pages),
        "sequence": pad_sequence,
    }
    return ToolOutcome(output_files=(written,), data=data)


def _impose(
    out: pikepdf.Pdf,
    source: pikepdf.Pdf,
    sequence: list[int],
    blank_size: tuple[float, float],
    gutter: float,
    fold_line: bool,
) -> None:
    for pair in batched(sequence, 2, strict=True):
        slots = [_slot(out, source, number) for number in pair]
        sizes = [(s.width, s.height) if s else blank_size for s in slots]
        height = max(h for _, h in sizes)
        left_width = sizes[0][0]
        placements = _placements(slots, sizes, (0.0, left_width + gutter), height)
        fold = _fold_stream(left_width + gutter / 2, height) if fold_line else b""
        add_sheet(out, left_width + gutter + sizes[1][0], height, placements, fold)


def _slot(out: pikepdf.Pdf, source: pikepdf.Pdf, number: int) -> PageForm | None:
    if number > len(source.pages):
        return None
    return import_page(out, source.pages[number - 1])


def _placements(
    slots: list[PageForm | None],
    sizes: list[tuple[float, float]],
    x_positions: tuple[float, float],
    height: float,
) -> list[Placement]:
    return [
        Placement(slot, 1.0, x, (height - size[1]) / 2)
        for slot, size, x in zip(slots, sizes, x_positions, strict=True)
        if slot is not None
    ]


def _fold_stream(x: float, height: float) -> bytes:
    return (
        f"q 0.6 G 0.5 w [3 3] 0 d {x:.4f} 0 m {x:.4f} {height:.4f} l S Q\n"
    ).encode()
