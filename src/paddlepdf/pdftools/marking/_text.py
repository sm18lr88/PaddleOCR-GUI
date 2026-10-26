"""Positioned single-line text drawing for numbering, header/footer and Bates."""

from enum import StrEnum

from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen.canvas import Canvas

from paddlepdf.pdftools.marking._overlay import Painter


class Position(StrEnum):
    TOP_LEFT = "top-left"
    TOP_CENTER = "top-center"
    TOP_RIGHT = "top-right"
    BOTTOM_LEFT = "bottom-left"
    BOTTOM_CENTER = "bottom-center"
    BOTTOM_RIGHT = "bottom-right"


def draw_text(
    canvas: Canvas,
    text: str,
    position: Position,
    page_size: tuple[float, float],
    font_size: float,
    margin: float,
) -> None:
    visible_w, visible_h = page_size
    font = "Helvetica"
    text_w = stringWidth(text, font, font_size)
    horizontal = position.value.split("-")[1]
    if horizontal == "left":
        x = margin
    elif horizontal == "center":
        x = (visible_w - text_w) / 2
    else:
        x = visible_w - margin - text_w
    y = visible_h - margin - font_size if position.value.startswith("top") else margin
    canvas.saveState()
    canvas.setFillGray(0)
    canvas.setFont(font, font_size)
    canvas.drawString(x, y, text)
    canvas.restoreState()


def text_painter(
    template: str,
    position: Position,
    font_size: float,
    margin: float,
    first_number: int = 1,
) -> Painter:
    """Painter expanding ``{n}`` (first_number + index) and ``{total}``."""

    def paint(
        canvas: Canvas, visible_w: float, visible_h: float, index: int, total: int
    ) -> None:
        text = template.replace("{n}", str(first_number + index))
        text = text.replace("{total}", str(total))
        draw_text(canvas, text, position, (visible_w, visible_h), font_size, margin)

    return paint
