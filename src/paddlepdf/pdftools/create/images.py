"""pdf_images_to_pdf: one page per image, in the order given."""

from typing import Annotated, Literal

from pydantic import Field
from reportlab.pdfgen.canvas import Canvas

from paddlepdf.pdftools.common import input_path, output_path
from paddlepdf.pdftools.contract import ToolOutcome
from paddlepdf.pdftools.create.imaging import (
    IMAGE_SUFFIXES,
    Fit,
    ImageOrientation,
    draw_image_page,
    prepare_image,
)
from paddlepdf.pdftools.create.styles import PageSize


def pdf_images_to_pdf(
    input_files: Annotated[
        list[str],
        Field(
            min_length=1,
            description="Images (JPG/PNG/WebP/BMP/GIF/TIFF), one page each, in order.",
        ),
    ],
    output_file: Annotated[str, Field(description="Path of the PDF to write.")],
    page_size: Annotated[
        PageSize | Literal["image"],
        Field(description="'image': page = image pixels as points; else a paper size."),
    ] = "image",
    orientation: Annotated[
        ImageOrientation,
        Field(
            description="Paper orientation; 'auto' follows each image's aspect ratio."
        ),
    ] = "auto",
    fit: Annotated[
        Fit,
        Field(
            description="contain (keep aspect), shrink (contain, no upscale), stretch."
        ),
    ] = "contain",
    margin_mm: Annotated[
        float, Field(ge=0, le=100, description="White margin around each image in mm.")
    ] = 0,
) -> ToolOutcome:
    sources = [input_path(value, IMAGE_SUFFIXES) for value in input_files]
    target = output_path(output_file, *sources)
    prepared = [prepare_image(source.read_bytes(), str(source)) for source in sources]
    canvas = Canvas(str(target))
    for image in prepared:
        draw_image_page(
            canvas,
            image,
            None if page_size == "image" else page_size,
            orientation,
            fit,
            margin_mm,
        )
    canvas.save()
    return ToolOutcome(
        output_files=(str(target),),
        data={
            "page_count": len(prepared),
            "images": [
                {"file": str(source), "width": image.width, "height": image.height}
                for source, image in zip(sources, prepared, strict=True)
            ],
        },
    )
