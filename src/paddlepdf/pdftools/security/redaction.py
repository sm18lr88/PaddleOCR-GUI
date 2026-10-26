"""True redaction: every affected page is rebuilt as an image with opaque boxes.

Rasterizing guarantees the covered text, its glyphs, hidden runs, and annotation
content are gone from the output; the trade-off is that the rest of the text on an
affected page also stops being selectable and becomes a bitmap at ``dpi``.
Untouched pages keep their vector content.
"""

import math
import zlib
from pathlib import Path
from typing import Annotated, SupportsFloat, cast

import pikepdf
from PIL import Image, ImageDraw
from pydantic import BaseModel, ConfigDict, Field, JsonValue

from paddlepdf.pdftools.common import (
    input_path,
    open_pdf,
    output_path,
    parse_page_ranges,
    save_pdf,
)
from paddlepdf.pdftools.contract import PdfToolError, ToolOutcome
from paddlepdf.pdftools.pdfium import Box, find_text_boxes, page_count, render_page
from paddlepdf.pdftools.security._params import InputFile, InputPassword, OutputFile

_SEARCH_PADDING = 1.0
_IMAGE_NAME = "/RedactedPage"
_LEAKY_PAGE_KEYS = ("/Annots", "/Thumb", "/PieceInfo", "/StructParents")


class RedactRegion(BaseModel):
    model_config = ConfigDict(frozen=True)

    page: Annotated[int, Field(ge=1, description="1-based page number.")]
    x: Annotated[
        float, Field(description="Left edge in PDF points (origin bottom-left).")
    ]
    y: Annotated[float, Field(description="Bottom edge in PDF points.")]
    width: Annotated[float, Field(gt=0, description="Box width in PDF points.")]
    height: Annotated[float, Field(gt=0, description="Box height in PDF points.")]


def _number(value: object) -> float:
    return float(cast("SupportsFloat", value))


def _crop(page: pikepdf.Page) -> Box:
    x0, y0, x1, y1 = (_number(value) for value in page.cropbox)
    return min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)


def _burn_boxes(image: Image.Image, crop: Box, boxes: list[Box], scale: float) -> None:
    draw = ImageDraw.Draw(image)
    for left, bottom, right, top in boxes:
        draw.rectangle(
            (
                math.floor((left - crop[0]) * scale),
                math.floor((crop[3] - top) * scale),
                math.ceil((right - crop[0]) * scale),
                math.ceil((crop[3] - bottom) * scale),
            ),
            fill=(0, 0, 0),
        )


def _rasterize(
    pdf: pikepdf.Pdf,
    source: Path,
    index: int,
    boxes: list[Box],
    dpi: int,
    password: str | None,
) -> None:
    page = pdf.pages[index]
    crop = _crop(page)
    rendered = render_page(source, index, dpi=dpi, password=password).convert("RGB")
    # pdfium renders with /Rotate applied clockwise; undo it to draw in user space.
    image = rendered.rotate(page.rotation % 360, expand=True)
    _burn_boxes(image, crop, boxes, dpi / 72)
    xobject = pikepdf.Stream(pdf, zlib.compress(image.tobytes()))
    xobject.Type = pikepdf.Name.XObject
    xobject.Subtype = pikepdf.Name.Image
    xobject.Width = image.width
    xobject.Height = image.height
    xobject.ColorSpace = pikepdf.Name.DeviceRGB
    xobject.BitsPerComponent = 8
    xobject.Filter = pikepdf.Name.FlateDecode
    width, height = crop[2] - crop[0], crop[3] - crop[1]
    content = f"q {width:.4f} 0 0 {height:.4f} {crop[0]:.4f} {crop[1]:.4f} cm "
    content += f"{_IMAGE_NAME} Do Q"
    page.obj.Resources = pikepdf.Dictionary(
        XObject=pikepdf.Dictionary({_IMAGE_NAME: xobject})
    )
    page.obj.Contents = pdf.make_stream(content.encode("ascii"))
    for key in _LEAKY_PAGE_KEYS:
        if key in page.obj:
            del page.obj[key]


def _collect_boxes(
    source: Path,
    count: int,
    search_text: str | None,
    regions: list[RedactRegion],
    options: tuple[str, bool, bool, str | None],
) -> tuple[dict[int, list[Box]], list[JsonValue]]:
    pages, match_case, whole_word, password = options
    boxes: dict[int, list[Box]] = {}
    report: list[JsonValue] = []
    if search_text:
        selected = set(parse_page_ranges(pages, count))
        found = find_text_boxes(
            source,
            search_text,
            match_case=match_case,
            whole_word=whole_word,
            password=password,
        )
        for index in sorted(found.keys() & selected):
            for left, bottom, right, top in found[index]:
                padded = (
                    left - _SEARCH_PADDING,
                    bottom - _SEARCH_PADDING,
                    right + _SEARCH_PADDING,
                    top + _SEARCH_PADDING,
                )
                boxes.setdefault(index, []).append(padded)
                report.append(_box_report(index, padded, "search"))
    for region in regions:
        if region.page > count:
            msg = f"Region page {region.page} is outside the document (1-{count})"
            raise PdfToolError(msg)
        box = (region.x, region.y, region.x + region.width, region.y + region.height)
        boxes.setdefault(region.page - 1, []).append(box)
        report.append(_box_report(region.page - 1, box, "region"))
    return boxes, report


def _box_report(index: int, box: Box, source: str) -> dict[str, JsonValue]:
    return {
        "page": index + 1,
        "x": round(box[0], 2),
        "y": round(box[1], 2),
        "width": round(box[2] - box[0], 2),
        "height": round(box[3] - box[1], 2),
        "source": source,
    }


def pdf_redact(
    input_file: InputFile,
    output_file: OutputFile,
    search_text: Annotated[
        str | None, Field(description="Redact every occurrence of this text.")
    ] = None,
    regions: Annotated[
        list[RedactRegion] | None,
        Field(description="Explicit page rectangles to redact, in PDF points."),
    ] = None,
    pages: Annotated[
        str, Field(description="Pages searched for search_text, e.g. '1,3-5,last'.")
    ] = "all",
    match_case: Annotated[
        bool, Field(description="Case-sensitive text search.")
    ] = False,
    whole_word: Annotated[bool, Field(description="Match whole words only.")] = False,
    dpi: Annotated[
        int, Field(ge=72, le=600, description="Resolution for rebuilt redacted pages.")
    ] = 150,
    password: InputPassword = None,
) -> ToolOutcome:
    if not search_text and not regions:
        msg = "Provide search_text and/or regions to redact"
        raise PdfToolError(msg)
    source = input_path(input_file)
    target = output_path(output_file, source)
    count = page_count(source, password)
    boxes, report = _collect_boxes(
        source,
        count,
        search_text,
        regions or [],
        (pages, match_case, whole_word, password),
    )
    warnings: list[str] = []
    with open_pdf(source, password) as pdf:
        for index in sorted(boxes):
            _rasterize(pdf, source, index, boxes[index], dpi, password)
        if boxes and "/StructTreeRoot" in pdf.Root:
            del pdf.Root.StructTreeRoot
            warnings.append("Removed the tag structure tree so it cannot leak text")
        if boxes and "/AcroForm" in pdf.Root:
            warnings.append("Form field values are not redacted; flatten forms first")
        written = save_pdf(pdf, target)
    if not boxes:
        warnings.append("Nothing matched; wrote an unredacted copy")
    data: dict[str, JsonValue] = {
        "redaction_count": len(report),
        "rasterized_pages": [index + 1 for index in sorted(boxes)],
        "redactions": report,
    }
    return ToolOutcome(output_files=(written,), data=data, warnings=tuple(warnings))
