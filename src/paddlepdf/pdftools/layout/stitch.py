"""pdf_stitch_canvas: join every page into one continuous single-page canvas."""

from typing import Annotated, Literal

import pikepdf
from pydantic import Field, JsonValue

from paddlepdf.pdftools.common import input_path, open_pdf, output_path, save_pdf
from paddlepdf.pdftools.contract import PdfToolError, ToolOutcome
from paddlepdf.pdftools.layout.compose import Placement, add_sheet, import_page


def pdf_stitch_canvas(
    input_file: Annotated[str, Field(description="Path to the source PDF.")],
    output_file: Annotated[
        str, Field(description="Path of the one-page PDF to write.")
    ],
    direction: Annotated[
        Literal["vertical", "horizontal"],
        Field(description="Stack pages top-to-bottom or lay them left-to-right."),
    ] = "vertical",
    margin_pt: Annotated[
        float, Field(ge=0, description="Margin around the canvas in points.")
    ] = 0.0,
    spacing_pt: Annotated[
        float, Field(ge=0, description="Gap between pages in points.")
    ] = 0.0,
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
    out = pikepdf.new()
    forms = [import_page(out, page) for page in source.pages]
    gaps = spacing_pt * (len(forms) - 1)
    placements: list[Placement] = []
    if direction == "horizontal":
        canvas_w = sum(f.width for f in forms) + 2 * margin_pt + gaps
        canvas_h = max(f.height for f in forms) + 2 * margin_pt
        x = margin_pt
        for form in forms:
            placements.append(
                Placement(
                    form,
                    1.0,
                    x,
                    margin_pt + (canvas_h - 2 * margin_pt - form.height) / 2,
                )
            )
            x += form.width + spacing_pt
    else:
        canvas_w = max(f.width for f in forms) + 2 * margin_pt
        canvas_h = sum(f.height for f in forms) + 2 * margin_pt + gaps
        y = canvas_h - margin_pt
        for form in forms:
            y -= form.height
            placements.append(
                Placement(
                    form,
                    1.0,
                    margin_pt + (canvas_w - 2 * margin_pt - form.width) / 2,
                    y,
                )
            )
            y -= spacing_pt
    add_sheet(out, canvas_w, canvas_h, placements)
    written = save_pdf(out, target)
    data: dict[str, JsonValue] = {
        "source_pages": len(forms),
        "width_pt": canvas_w,
        "height_pt": canvas_h,
    }
    return ToolOutcome(output_files=(written,), data=data)
