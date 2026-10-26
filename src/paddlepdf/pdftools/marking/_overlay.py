"""Overlay machinery for marking tools: draw with reportlab, merge with pikepdf."""

from collections.abc import Callable
from io import BytesIO
from typing import Final

import pikepdf
from pikepdf import Page, Rectangle
from reportlab.lib.colors import Color
from reportlab.pdfgen.canvas import Canvas

from paddlepdf.pdftools.common import (
    input_path,
    open_pdf,
    output_path,
    parse_page_ranges,
    save_pdf,
)
from paddlepdf.pdftools.contract import PdfToolError, ToolOutcome

type Painter = Callable[[Canvas, float, float, int, int], None]

_NAMED_COLORS: Final = {
    "red": (1.0, 0.0, 0.0),
    "blue": (0.0, 0.0, 1.0),
    "green": (0.0, 1.0, 0.0),
    "black": (0.0, 0.0, 0.0),
    "white": (1.0, 1.0, 1.0),
    "gray": (0.5, 0.5, 0.5),
    "grey": (0.5, 0.5, 0.5),
}
_HEX_LENGTH: Final = 7
_QUARTER_TURNS: Final = frozenset({0, 90, 180, 270})


def parse_color(value: str) -> tuple[float, float, float]:
    """Accept a basic color name or ``#RRGGBB``."""
    text = value.strip().lower()
    if text in _NAMED_COLORS:
        return _NAMED_COLORS[text]
    if text.startswith("#") and len(text) == _HEX_LENGTH:
        try:
            red, green, blue = (int(text[i : i + 2], 16) / 255 for i in (1, 3, 5))
        except ValueError:
            pass
        else:
            return red, green, blue
    names = ", ".join(_NAMED_COLORS)
    msg = f"Unsupported color {value!r}; use a name ({names}) or #RRGGBB"
    raise PdfToolError(msg)


def to_reportlab_color(value: str) -> Color:
    return Color(*parse_color(value))


def _rotation(page: Page) -> int:
    node = page.obj
    while node is not None:
        if "/Rotate" in node:
            return int(node["/Rotate"]) % 360
        parent = node.get("/Parent")
        node = parent if isinstance(parent, pikepdf.Dictionary) else None
    return 0


def _paint_page(pdf: pikepdf.Pdf, index: int, painter: Painter) -> None:
    total = len(pdf.pages)
    page = Page(pdf.pages[index])
    first_x, first_y, second_x, second_y = (float(v) for v in page.mediabox)
    left, right = sorted((first_x, second_x))
    bottom, top = sorted((first_y, second_y))
    width, height = right - left, top - bottom
    rotate = _rotation(page)
    if rotate not in _QUARTER_TURNS:
        msg = f"Page {index + 1} has unsupported /Rotate {rotate}"
        raise PdfToolError(msg)
    visible_w, visible_h = (height, width) if rotate in {90, 270} else (width, height)
    buffer = BytesIO()
    # qpdf's overlay placement undoes /Rotate, so draw in as-displayed coordinates.
    canvas = Canvas(buffer, pagesize=(visible_w, visible_h))
    painter(canvas, visible_w, visible_h, index, total)
    canvas.showPage()
    canvas.save()
    with pikepdf.open(BytesIO(buffer.getvalue())) as overlay:
        page.add_overlay(Page(overlay.pages[0]), Rectangle(left, bottom, right, top))


def mark_document(
    input_file: str,
    output_file: str,
    pages: str,
    password: str | None,
    painter: Painter,
) -> ToolOutcome:
    source = input_path(input_file)
    target = output_path(output_file, source)
    with open_pdf(source, password) as pdf:
        indexes = sorted(set(parse_page_ranges(pages, len(pdf.pages))))
        for index in indexes:
            _paint_page(pdf, index, painter)
        saved = save_pdf(pdf, target)
    return ToolOutcome(
        output_files=(saved,),
        data={"pages_marked": [index + 1 for index in indexes]},
    )
