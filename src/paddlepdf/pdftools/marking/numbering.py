from typing import Annotated

from pydantic import Field
from reportlab.pdfgen.canvas import Canvas

from paddlepdf.pdftools.contract import ToolOutcome
from paddlepdf.pdftools.marking._overlay import mark_document
from paddlepdf.pdftools.marking._text import Position, draw_text, text_painter


def pdf_page_numbers(
    input_file: Annotated[str, Field(description="Source PDF path.")],
    output_file: Annotated[str, Field(description="Destination PDF path.")],
    position: Annotated[
        Position, Field(description="Where the number is drawn.")
    ] = Position.BOTTOM_RIGHT,
    label_format: Annotated[
        str,
        Field(description="Template; {n} is the page number, {total} the page count."),
    ] = "Page {n} of {total}",
    start_number: Annotated[
        int, Field(description="Number shown on the first page.")
    ] = 1,
    font_size: Annotated[float, Field(gt=0, description="Font size in points.")] = 12.0,
    margin: Annotated[
        float, Field(ge=0, description="Distance from the page edge in points.")
    ] = 30.0,
    pages: Annotated[
        str, Field(description='Pages to number, e.g. "2-last" or "all".')
    ] = "all",
    password: Annotated[
        str | None, Field(description="Password of an encrypted input.")
    ] = None,
) -> ToolOutcome:
    painter = text_painter(label_format, position, font_size, margin, start_number)
    return mark_document(input_file, output_file, pages, password, painter)


def pdf_header_footer(
    input_file: Annotated[str, Field(description="Source PDF path.")],
    output_file: Annotated[str, Field(description="Destination PDF path.")],
    text: Annotated[
        str, Field(description="Header/footer text; {n} and {total} are expanded.")
    ],
    position: Annotated[
        Position, Field(description="Header (top-*) or footer (bottom-*) slot.")
    ] = Position.TOP_LEFT,
    font_size: Annotated[float, Field(gt=0, description="Font size in points.")] = 12.0,
    margin: Annotated[
        float, Field(ge=0, description="Distance from the page edge in points.")
    ] = 40.0,
    pages: Annotated[
        str, Field(description='Pages such as "1,3-5,last" or "all".')
    ] = "all",
    password: Annotated[
        str | None, Field(description="Password of an encrypted input.")
    ] = None,
) -> ToolOutcome:
    painter = text_painter(text, position, font_size, margin)
    return mark_document(input_file, output_file, pages, password, painter)


def pdf_bates(
    input_file: Annotated[str, Field(description="Source PDF path.")],
    output_file: Annotated[str, Field(description="Destination PDF path.")],
    prefix: Annotated[
        str, Field(description="Text placed before the number, e.g. ACME-.")
    ] = "",
    start_number: Annotated[
        int, Field(ge=0, description="Number stamped on the first page.")
    ] = 1,
    padding: Annotated[
        int, Field(ge=1, description="Minimum digits (zero padded).")
    ] = 6,
    position: Annotated[
        Position, Field(description="Where the Bates label is drawn.")
    ] = Position.BOTTOM_RIGHT,
    font_size: Annotated[float, Field(gt=0, description="Font size in points.")] = 10.0,
    margin: Annotated[
        float, Field(ge=0, description="Distance from the page edge in points.")
    ] = 30.0,
    pages: Annotated[
        str,
        Field(description="Pages to stamp; numbers still follow document page order."),
    ] = "all",
    password: Annotated[
        str | None, Field(description="Password of an encrypted input.")
    ] = None,
) -> ToolOutcome:
    def paint(
        canvas: Canvas, visible_w: float, visible_h: float, index: int, _total: int
    ) -> None:
        label = f"{prefix}{start_number + index:0{padding}d}"
        draw_text(canvas, label, position, (visible_w, visible_h), font_size, margin)

    return mark_document(input_file, output_file, pages, password, paint)
