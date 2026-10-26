"""pdf_nup: put 2, 4, 9, or 16 pages on each output sheet."""

from itertools import batched
from typing import Annotated, Literal

import pikepdf
from pydantic import Field, JsonValue

from paddlepdf.pdftools.common import input_path, open_pdf, output_path, save_pdf
from paddlepdf.pdftools.contract import PdfToolError, ToolOutcome
from paddlepdf.pdftools.layout.compose import (
    Placement,
    add_sheet,
    import_page,
    page_size,
)

_TWO_UP = 2
_GRIDS = {2: (1, 2), 4: (2, 2), 9: (3, 3), 16: (4, 4)}


def pdf_nup(
    input_file: Annotated[str, Field(description="Path to the source PDF.")],
    output_file: Annotated[str, Field(description="Path of the N-up PDF to write.")],
    nup: Annotated[Literal[2, 4, 9, 16], Field(description="Pages per sheet.")] = 2,
    ordering: Annotated[
        Literal["horizontal", "vertical"],
        Field(description="Fill the grid row by row or column by column."),
    ] = "horizontal",
    margin_pt: Annotated[
        float, Field(ge=0, description="Sheet margin in points.")
    ] = 18.0,
    spacing_pt: Annotated[
        float, Field(ge=0, description="Gap between cells in points.")
    ] = 10.0,
    draw_borders: Annotated[
        bool, Field(description="Stroke a thin border around each placed page.")
    ] = False,
    password: Annotated[
        str | None, Field(description="Password if the input is encrypted.")
    ] = None,
) -> ToolOutcome:
    source_path = input_path(input_file)
    target = output_path(output_file, source_path)
    source = open_pdf(source_path, password)
    if len(source.pages) == 0:
        msg = "Document contains no pages"
        raise PdfToolError(msg)
    rows, cols = _GRIDS[nup]
    sheet_w, sheet_h = page_size(source.pages[0])
    if nup == _TWO_UP:
        sheet_w, sheet_h = max(sheet_w, sheet_h), min(sheet_w, sheet_h)
    cell_w = (sheet_w - 2 * margin_pt - spacing_pt * (cols - 1)) / cols
    cell_h = (sheet_h - 2 * margin_pt - spacing_pt * (rows - 1)) / rows
    if cell_w <= 0 or cell_h <= 0:
        msg = "margin_pt and spacing_pt leave no room for the pages"
        raise PdfToolError(msg)
    out = pikepdf.new()
    for chunk in batched(source.pages, rows * cols, strict=False):
        placements: list[Placement] = []
        borders = ""
        for index, page in enumerate(chunk):
            row, col = (
                (index // cols, index % cols)
                if ordering == "horizontal"
                else (index % rows, index // rows)
            )
            form = import_page(out, page)
            scale = min(cell_w / form.width, cell_h / form.height)
            width, height = form.width * scale, form.height * scale
            x = margin_pt + col * (cell_w + spacing_pt) + (cell_w - width) / 2
            y = (
                sheet_h
                - margin_pt
                - (row + 1) * cell_h
                - row * spacing_pt
                + (cell_h - height) / 2
            )
            placements.append(Placement(form, scale, x, y))
            if draw_borders:
                borders += (
                    f"q 0 G 0.5 w {x:.4f} {y:.4f} {width:.4f} {height:.4f} re S Q\n"
                )
        add_sheet(out, sheet_w, sheet_h, placements, borders.encode())
    written = save_pdf(out, target)
    data: dict[str, JsonValue] = {
        "source_pages": len(source.pages),
        "output_pages": len(out.pages),
        "nup": nup,
    }
    return ToolOutcome(output_files=(written,), data=data)
