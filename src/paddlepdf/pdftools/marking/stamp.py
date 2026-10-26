import base64
import binascii
from io import BytesIO
from typing import Annotated

from pydantic import Field
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen.canvas import Canvas

from paddlepdf.pdftools.common import input_path
from paddlepdf.pdftools.contract import PdfToolError, ToolOutcome
from paddlepdf.pdftools.marking._overlay import mark_document
from paddlepdf.pdftools.marking.watermark import IMAGE_SUFFIXES


def _stamp_image(image_file: str | None, image_base64: str | None) -> ImageReader:
    if image_file:
        return ImageReader(str(input_path(image_file, IMAGE_SUFFIXES)))
    if image_base64:
        try:
            return ImageReader(BytesIO(base64.b64decode(image_base64, validate=True)))
        except binascii.Error as error:
            msg = f"image_base64 is not valid base64: {error}"
            raise PdfToolError(msg) from error
    msg = "Provide image_file or image_base64 for the stamp"
    raise PdfToolError(msg)


def pdf_stamp(
    input_file: Annotated[str, Field(description="Source PDF path.")],
    output_file: Annotated[str, Field(description="Destination PDF path.")],
    image_file: Annotated[
        str | None, Field(description="Stamp image path (PNG/JPEG/...); alpha is kept.")
    ] = None,
    image_base64: Annotated[
        str | None,
        Field(description="Inline base64 image data, used when image_file is absent."),
    ] = None,
    x: Annotated[
        float,
        Field(description="Left edge in points from the bottom-left of the page."),
    ] = 50.0,
    y: Annotated[
        float,
        Field(description="Bottom edge in points from the bottom-left of the page."),
    ] = 50.0,
    width: Annotated[
        float, Field(gt=0, description="Rendered width in points.")
    ] = 150.0,
    height: Annotated[
        float, Field(gt=0, description="Rendered height in points.")
    ] = 50.0,
    opacity: Annotated[
        float, Field(ge=0, le=1, description="0 transparent to 1 opaque.")
    ] = 1.0,
    pages: Annotated[
        str, Field(description='Pages such as "1,3-5,last" or "all".')
    ] = "all",
    password: Annotated[
        str | None, Field(description="Password of an encrypted input.")
    ] = None,
) -> ToolOutcome:
    reader = _stamp_image(image_file, image_base64)

    def paint(canvas: Canvas, _w: float, _h: float, _index: int, _total: int) -> None:
        canvas.saveState()
        canvas.setFillAlpha(opacity)
        canvas.drawImage(reader, x, y, width, height, mask="auto")
        canvas.restoreState()

    return mark_document(input_file, output_file, pages, password, paint)
