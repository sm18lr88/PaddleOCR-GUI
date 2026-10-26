from typing import Annotated

from pydantic import Field
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen.canvas import Canvas

from paddlepdf.pdftools.common import input_path
from paddlepdf.pdftools.contract import PdfToolError, ToolOutcome
from paddlepdf.pdftools.marking._overlay import (
    mark_document,
    to_reportlab_color,
)

IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".bmp", ".gif", ".tif", ".tiff", ".webp")
_MAX_TEXT_FRACTION = 0.85
_BASELINE_SHIFT = 0.35


def pdf_watermark(
    input_file: Annotated[str, Field(description="Source PDF path.")],
    output_file: Annotated[str, Field(description="Destination PDF path.")],
    text: Annotated[
        str | None, Field(description="Watermark text (Latin-1 characters, Helvetica).")
    ] = None,
    image_file: Annotated[
        str | None,
        Field(description="Watermark image path (PNG/JPEG/...); alpha is kept."),
    ] = None,
    opacity: Annotated[
        float, Field(ge=0, le=1, description="0 transparent to 1 opaque.")
    ] = 0.2,
    angle: Annotated[
        float, Field(description="Counter-clockwise rotation in degrees.")
    ] = 45.0,
    font_size: Annotated[
        float | None,
        Field(
            gt=0,
            description="Text size in points (default 54, shrunk to fit the page).",
        ),
    ] = None,
    color: Annotated[
        str,
        Field(
            description="Text color: red, blue, green, black, white, gray or #RRGGBB."
        ),
    ] = "gray",
    image_scale: Annotated[
        float, Field(gt=0, le=1, description="Image width as a fraction of page width.")
    ] = 0.5,
    pages: Annotated[
        str, Field(description='Pages such as "1,3-5,last" or "all".')
    ] = "all",
    password: Annotated[
        str | None, Field(description="Password of an encrypted input.")
    ] = None,
) -> ToolOutcome:
    if not text and not image_file:
        msg = "Provide text and/or image_file for the watermark"
        raise PdfToolError(msg)
    reader = (
        ImageReader(str(input_path(image_file, IMAGE_SUFFIXES))) if image_file else None
    )
    fill = to_reportlab_color(color)

    def paint(
        canvas: Canvas, visible_w: float, visible_h: float, _index: int, _total: int
    ) -> None:
        canvas.saveState()
        canvas.setFillAlpha(opacity)
        canvas.translate(visible_w / 2, visible_h / 2)
        canvas.rotate(angle)
        if reader is not None:
            image_w, image_h = reader.getSize()
            width = visible_w * image_scale
            height = width * image_h / image_w
            canvas.drawImage(
                reader, -width / 2, -height / 2, width, height, mask="auto"
            )
        if text:
            size = font_size or 54.0
            text_w = stringWidth(text, "Helvetica", size)
            if text_w > visible_w * _MAX_TEXT_FRACTION:
                size *= visible_w * _MAX_TEXT_FRACTION / text_w
            canvas.setFillColor(fill)
            canvas.setFont("Helvetica", size)
            canvas.drawCentredString(0, -size * _BASELINE_SHIFT, text)
        canvas.restoreState()

    return mark_document(input_file, output_file, pages, password, paint)
