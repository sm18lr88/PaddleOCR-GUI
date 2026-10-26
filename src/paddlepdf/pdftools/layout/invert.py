"""pdf_invert_colors: recolor pages with blend-mode layers, keeping vectors."""

from enum import StrEnum
from typing import Annotated

import pikepdf
from pydantic import Field, JsonValue

from paddlepdf.pdftools.common import (
    input_path,
    open_pdf,
    output_path,
    parse_page_ranges,
    save_pdf,
)
from paddlepdf.pdftools.contract import ToolOutcome
from paddlepdf.pdftools.layout.compose import add_resource, paint_over, paint_under

type Layer = tuple[str, tuple[float, float, float]]

_WHITE = (1.0, 1.0, 1.0)
_HALF = (0.5, 0.5, 0.5)


class InvertMode(StrEnum):
    DARK_MODE = "dark_mode"
    TRUE_INVERT = "true_invert"
    HIGH_CONTRAST = "high_contrast"
    SEPIA = "sepia"


def _layers(mode: InvertMode) -> list[Layer]:
    """Blend layers painted over the page, applied to the rendered colors in order."""
    match mode:
        case InvertMode.TRUE_INVERT:
            return [("Difference", _WHITE)]
        case InvertMode.DARK_MODE:
            # Difference gives u = 1 - v; Screen(0.2/0.9) then Multiply(0.9) maps it
            # to 0.2 + 0.7 u, the same curve PaperPilot applied to each color.
            lift = 0.2 / 0.9
            return [
                ("Difference", _WHITE),
                ("Screen", (lift, lift, lift)),
                ("Multiply", (0.9, 0.9, 0.9)),
            ]
        case InvertMode.HIGH_CONTRAST:
            # Burn zeroes the lower half, then repeated Dodge doubles anything left
            # to 1: a per-channel threshold at 0.5 of the inverted page.
            return [
                ("Difference", _WHITE),
                ("ColorBurn", _HALF),
                *[("ColorDodge", _HALF)] * 8,
            ]
        case InvertMode.SEPIA:
            return [("Multiply", (0.98, 0.94, 0.90))]


def pdf_invert_colors(
    input_file: Annotated[str, Field(description="Path to the source PDF.")],
    output_file: Annotated[
        str, Field(description="Path of the recolored PDF to write.")
    ],
    mode: Annotated[
        InvertMode,
        Field(description="dark_mode, true_invert, high_contrast, or sepia."),
    ] = InvertMode.DARK_MODE,
    pages: Annotated[
        str, Field(description='Pages to recolor, 1-based: "all", "1,3-5", "last".')
    ] = "all",
    password: Annotated[
        str | None, Field(description="Password if the input is encrypted.")
    ] = None,
) -> ToolOutcome:
    source_path = input_path(input_file)
    target = output_path(output_file, source_path)
    pdf = open_pdf(source_path, password)
    targets = sorted(set(parse_page_ranges(pages, len(pdf.pages))))
    layers = _layers(mode)
    states = {
        blend: pdf.make_indirect(
            pikepdf.Dictionary(
                Type=pikepdf.Name.ExtGState, BM=pikepdf.Name(f"/{blend}")
            )
        )
        for blend in dict.fromkeys(blend for blend, _ in layers)
    }
    for index in targets:
        page = pdf.pages[index]
        left, bottom, right, top = (float(value) for value in page.mediabox)
        rect = f"{left:.4f} {bottom:.4f} {right - left:.4f} {top - bottom:.4f} re f\n"
        # Blend modes need an opaque backdrop; unpainted paper counts as transparent.
        paint_under(pdf, page, f"1 g {rect}".encode())
        operations = ""
        for blend, (red, green, blue) in layers:
            add_resource(page, "/ExtGState", f"/Inv{blend}", states[blend])
            operations += f"/Inv{blend} gs {red:.4f} {green:.4f} {blue:.4f} rg {rect}"
        paint_over(pdf, page, operations.encode())
    written = save_pdf(pdf, target)
    data: dict[str, JsonValue] = {
        "mode": mode.value,
        "recolored_pages": [i + 1 for i in targets],
    }
    return ToolOutcome(output_files=(written,), data=data)
