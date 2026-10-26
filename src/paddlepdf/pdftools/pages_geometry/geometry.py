"""Page-box tools: crop, scale to a paper size, and rotate toward an orientation."""

from enum import StrEnum
from typing import Annotated, Final

import pikepdf
from pydantic import Field, JsonValue

from paddlepdf.pdftools.common import (
    input_path,
    open_pdf,
    output_path,
    parse_page_ranges,
    save_pdf,
)
from paddlepdf.pdftools.contract import PdfToolError, ToolOutcome

PAGE_SIZES: Final[dict[str, tuple[float, float]]] = {
    "A3": (841.89, 1190.55),
    "A4": (595.28, 841.89),
    "A5": (419.53, 595.28),
    "LETTER": (612.0, 792.0),
    "LEGAL": (612.0, 1008.0),
    "TABLOID": (792.0, 1224.0),
}
CROP_VALUES: Final = 4


class TargetSize(StrEnum):
    A3 = "A3"
    A4 = "A4"
    A5 = "A5"
    LETTER = "LETTER"
    LEGAL = "LEGAL"
    TABLOID = "TABLOID"
    ORIGINAL = "ORIGINAL"


class Orientation(StrEnum):
    PORTRAIT = "portrait"
    LANDSCAPE = "landscape"
    AUTO = "auto"


def media_box(page: pikepdf.Page) -> tuple[float, float, float, float]:
    left, bottom, right, top = (float(value) for value in page.mediabox)
    return left, bottom, right, top


def parse_crop_box(spec: str) -> tuple[float, float, float, float]:
    parts = [part.strip() for part in spec.split(",")]
    try:
        values = [float(part) for part in parts]
    except ValueError as error:
        msg = f"Invalid crop box {spec!r}; use 'left,bottom,right,top' in PDF points"
        raise PdfToolError(msg) from error
    if len(values) != CROP_VALUES:
        msg = f"Invalid crop box {spec!r}; expected 4 comma-separated numbers"
        raise PdfToolError(msg)
    left, bottom, right, top = values
    if left >= right or bottom >= top:
        msg = "Invalid crop box dimensions: need left < right and bottom < top"
        raise PdfToolError(msg)
    return left, bottom, right, top


def pdf_crop(
    input_file: Annotated[str, Field(description="Input PDF path.")],
    output_file: Annotated[str, Field(description="Output PDF path.")],
    crop_box: Annotated[
        str,
        Field(description="Crop rectangle 'left,bottom,right,top' in PDF points."),
    ],
    pages: Annotated[
        str, Field(description="1-based pages to crop, e.g. '1,3-5,last'.")
    ] = "all",
    password: Annotated[str | None, Field(description="PDF password.")] = None,
) -> ToolOutcome:
    """Set the CropBox of the selected pages."""
    source = input_path(input_file)
    target = output_path(output_file, source)
    box = parse_crop_box(crop_box)
    with open_pdf(source, password) as pdf:
        indexes = parse_page_ranges(pages, len(pdf.pages))
        for index in indexes:
            pdf.pages[index].obj["/CropBox"] = pikepdf.Array(list(box))
        saved = save_pdf(pdf, target)
    data: dict[str, JsonValue] = {
        "cropped_pages": [index + 1 for index in indexes],
        "crop_box": list(box),
    }
    return ToolOutcome(output_files=(saved,), data=data)


def _scale_page(
    pdf: pikepdf.Pdf,
    page: pikepdf.Page,
    target_size: TargetSize,
    scale_factor: float,
    *,
    keep_aspect: bool,
    center: bool,
) -> tuple[float, float]:
    x0, y0, x1, y1 = media_box(page)
    width, height = x1 - x0, y1 - y0
    if width <= 0 or height <= 0:
        return width, height
    base = PAGE_SIZES.get(target_size.value)
    if base is None:
        target_w, target_h = width * scale_factor, height * scale_factor
    else:
        target_w, target_h = base[0] * scale_factor, base[1] * scale_factor
    scale_x, scale_y = target_w / width, target_h / height
    if keep_aspect:
        scale_x = scale_y = min(scale_x, scale_y)
    shift_x = (target_w - width * scale_x) / 2 if center else 0.0
    shift_y = (target_h - height * scale_y) / 2 if center else 0.0
    offset_x = shift_x - x0 * scale_x
    offset_y = shift_y - y0 * scale_y
    matrix = f"q {scale_x:.6f} 0 0 {scale_y:.6f} {offset_x:.4f} {offset_y:.4f} cm\n"
    page.contents_add(pdf.make_stream(matrix.encode()), prepend=True)
    page.contents_add(pdf.make_stream(b"\nQ\n"), prepend=False)
    new_box = pikepdf.Array([0, 0, target_w, target_h])
    page.obj["/MediaBox"] = new_box
    if "/CropBox" in page.obj:
        page.obj["/CropBox"] = new_box
    return target_w, target_h


def pdf_scale_pages(
    input_file: Annotated[str, Field(description="Input PDF path.")],
    output_file: Annotated[str, Field(description="Output PDF path.")],
    target_size: Annotated[
        TargetSize,
        Field(
            description="Paper size to scale to, or ORIGINAL to keep each page size."
        ),
    ] = TargetSize.A4,
    scale_factor: Annotated[
        float, Field(gt=0, description="Extra multiplier on the target size.")
    ] = 1.0,
    maintain_aspect_ratio: Annotated[
        bool, Field(description="Scale uniformly instead of stretching.")
    ] = True,
    center_content: Annotated[
        bool, Field(description="Center the scaled content on the new page.")
    ] = True,
    password: Annotated[str | None, Field(description="PDF password.")] = None,
) -> ToolOutcome:
    """Scale every page's content and MediaBox to a standard size or a factor."""
    source = input_path(input_file)
    target = output_path(output_file, source)
    with open_pdf(source, password) as pdf:
        sizes = [
            _scale_page(
                pdf,
                page,
                target_size,
                scale_factor,
                keep_aspect=maintain_aspect_ratio,
                center=center_content,
            )
            for page in pdf.pages
        ]
        saved = save_pdf(pdf, target)
    return ToolOutcome(
        output_files=(saved,),
        data={"page_sizes": [[round(w, 2), round(h, 2)] for w, h in sizes]},
    )


def _rotation_for(page: pikepdf.Page, target: Orientation) -> int | None:
    x0, y0, x1, y1 = media_box(page)
    width, height = abs(x1 - x0), abs(y1 - y0)
    current = int(page.obj.get("/Rotate", 0)) % 360
    if current in {90, 270}:
        width, height = height, width
    wrong = width > height if target != Orientation.LANDSCAPE else height > width
    if not wrong:
        return None
    # Either quarter turn fixes the shape; prefer undoing an existing turn so text
    # ends upright (0) instead of upside down (180).
    options = ((current + 90) % 360, (current + 270) % 360)
    return 0 if 0 in options else options[0]


def pdf_auto_rotate(
    input_file: Annotated[str, Field(description="Input PDF path.")],
    output_file: Annotated[str, Field(description="Output PDF path.")],
    target_orientation: Annotated[
        Orientation,
        Field(description="portrait, landscape, or auto (treated as portrait)."),
    ] = Orientation.PORTRAIT,
    pages: Annotated[
        str, Field(description="1-based pages to consider, e.g. '1,3-5,last'.")
    ] = "all",
    password: Annotated[str | None, Field(description="PDF password.")] = None,
) -> ToolOutcome:
    """Rotate pages by 90 degrees when their shape does not match the orientation."""
    source = input_path(input_file)
    target = output_path(output_file, source)
    with open_pdf(source, password) as pdf:
        rotated: dict[str, JsonValue] = {}
        for index in parse_page_ranges(pages, len(pdf.pages)):
            new_rotation = _rotation_for(pdf.pages[index], target_orientation)
            if new_rotation is not None:
                pdf.pages[index].obj["/Rotate"] = new_rotation
                rotated[str(index + 1)] = new_rotation
        saved = save_pdf(pdf, target)
    data: dict[str, JsonValue] = {"rotated_pages": rotated}
    return ToolOutcome(output_files=(saved,), data=data)
