"""json_to_pdf: synthesize a PDF from PaperPilot's JSON document schema.

Schema (as emitted by PaperPilot's pdf_to_json): ``{"document_name": str, "pages":
[{"page_number": int, "text": str, "images": [{"id", "bbox": [x0, y0, x1, y1],
"base64_data" | "file_path"}]}]}``. Each JSON page starts a Letter page; text is
Helvetica 12 pt from (50, 750) with 15 pt leading, and images are drawn on top of the
first sheet at their PDF-point ``bbox`` (origin bottom-left).
"""

import base64
import binascii
from pathlib import Path
from typing import Annotated, Final, cast

from pydantic import BaseModel, Field, ValidationError
from reportlab.lib import utils as rl_utils
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen.canvas import Canvas

from paddlepdf.pdftools.common import input_path, output_path
from paddlepdf.pdftools.contract import PdfToolError, ToolOutcome
from paddlepdf.pdftools.create.imaging import (
    IMAGE_SUFFIXES,
    PreparedImage,
    prepare_image,
)

_FONT: Final = "Helvetica"
_FONT_SIZE: Final = 12
_LEFT: Final = 50
_TOP: Final = 750
_BOTTOM: Final = 50
_LEADING: Final = 15
_LINES_PER_SHEET: Final = (_TOP - _BOTTOM) // _LEADING + 1
_SCHEMA_HELP: Final = (
    "JSON in PaperPilot's pdf_to_json schema: {document_name, pages: [{page_number, "
    "text, images: [{id, bbox: [x0, y0, x1, y1], base64_data | file_path}]}]}."
)


class JsonImage(BaseModel):
    id: str = ""
    bbox: tuple[float, float, float, float] | None = None
    file_path: str | None = None
    base64_data: str | None = None


class JsonPage(BaseModel):
    page_number: int = 0
    text: str = ""
    images: list[JsonImage] = Field(default_factory=list[JsonImage])


class JsonDocument(BaseModel):
    document_name: str
    pages: list[JsonPage]


def _load_document(source: Path) -> JsonDocument:
    try:
        return JsonDocument.model_validate_json(source.read_bytes())
    except ValidationError as error:
        msg = f"{source} does not match the JSON document schema: {error}"
        raise PdfToolError(msg) from error


def _image_bytes(image: JsonImage, base_dir: Path) -> bytes | None:
    if image.base64_data:
        payload = image.base64_data
        if payload.startswith("data:"):
            payload = payload.partition(",")[2]
        try:
            return base64.b64decode(payload, validate=True)
        except binascii.Error as error:
            msg = f"Image {image.id!r} has invalid base64_data: {error}"
            raise PdfToolError(msg) from error
    if image.file_path:
        raw = Path(image.file_path)
        return input_path(
            str(raw if raw.is_absolute() else base_dir / raw), IMAGE_SUFFIXES
        ).read_bytes()
    return None


def _wrapped_lines(text: str) -> list[str]:
    width = letter[0] - 2 * _LEFT
    lines: list[str] = []
    for line in text.splitlines():
        wrapped = cast(
            "list[str]", rl_utils.simpleSplit(line, _FONT, _FONT_SIZE, width)
        )
        lines.extend(wrapped or [""])
    return lines


def _page_images(
    page: JsonPage, base_dir: Path, warnings: list[str]
) -> list[tuple[PreparedImage, tuple[float, float, float, float]]]:
    placed: list[tuple[PreparedImage, tuple[float, float, float, float]]] = []
    for image in page.images:
        data = _image_bytes(image, base_dir)
        if data is None:
            warnings.append(
                f"Page {page.page_number} image {image.id!r} has no data; skipped"
            )
        elif image.bbox is None:
            warnings.append(
                f"Page {page.page_number} image {image.id!r} has no bbox; skipped"
            )
        else:
            placed.append((prepare_image(data, f"image {image.id!r}"), image.bbox))
    return placed


def _draw_sheet(canvas: Canvas, chunk: list[str]) -> None:
    text = canvas.beginText(_LEFT, _TOP)
    text.setFont(_FONT, _FONT_SIZE, _LEADING)
    for line in chunk:
        text.textLine(line)
    canvas.drawText(text)


def _render_page(
    canvas: Canvas,
    lines: list[str],
    images: list[tuple[PreparedImage, tuple[float, float, float, float]]],
) -> tuple[int, int]:
    starts = range(0, max(len(lines), 1), _LINES_PER_SHEET)
    for chunk_index, start in enumerate(starts):
        _draw_sheet(canvas, lines[start : start + _LINES_PER_SHEET])
        if chunk_index == 0:
            for image, (x0, y0, x1, y1) in images:
                canvas.drawImage(image.reader, x0, y0, x1 - x0, y1 - y0)
        canvas.showPage()
    return len(starts), len(images)


def json_to_pdf(
    input_file: Annotated[
        str,
        Field(description=_SCHEMA_HELP),
    ],
    output_file: Annotated[str, Field(description="Path of the PDF to write.")],
) -> ToolOutcome:
    source = input_path(input_file, (".json",))
    target = output_path(output_file, source)
    document = _load_document(source)
    if not document.pages:
        msg = f"{source} has no pages to render"
        raise PdfToolError(msg)
    warnings: list[str] = []
    jobs = [
        (_wrapped_lines(page.text), _page_images(page, source.parent, warnings))
        for page in document.pages
    ]
    canvas = Canvas(str(target), pagesize=letter)
    canvas.setTitle(document.document_name)
    sheets = 0
    drawn = 0
    for lines, images in jobs:
        page_sheets, page_drawn = _render_page(canvas, lines, images)
        sheets += page_sheets
        drawn += page_drawn
    canvas.save()
    return ToolOutcome(
        output_files=(str(target),),
        data={
            "document_name": document.document_name,
            "source_pages": len(document.pages),
            "page_count": sheets,
            "images_drawn": drawn,
        },
        warnings=tuple(warnings),
    )
