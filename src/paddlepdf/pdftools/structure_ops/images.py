"""Raster output: extract embedded images and render pages to PNG/JPEG files."""

from enum import StrEnum
from typing import Annotated, Final

import pikepdf
from pydantic import Field, JsonValue

from paddlepdf.pdftools.common import (
    input_path,
    open_pdf,
    output_directory,
    parse_page_ranges,
)
from paddlepdf.pdftools.contract import ToolOutcome
from paddlepdf.pdftools.pdfium import page_count, render_page
from paddlepdf.pdftools.structure_ops._params import (
    InputFile,
    OutputDir,
    Pages,
    Password,
)

JPEG_QUALITY: Final = 90


class RenderFormat(StrEnum):
    PNG = "png"
    JPEG = "jpeg"


def pdf_extract_images(
    input_file: InputFile,
    output_dir: OutputDir,
    pages: Pages = "all",
    password: Password = None,
) -> ToolOutcome:
    source = input_path(input_file)
    directory = output_directory(output_dir)
    files: list[str] = []
    records: list[JsonValue] = []
    warnings: list[str] = []
    seen: set[tuple[int, int]] = set()
    with open_pdf(source, password) as pdf:
        for index in parse_page_ranges(pages, len(pdf.pages)):
            xobjects = pdf.pages[index].get_images()
            names = list(xobjects.keys())
            for key in names:
                name = str(key)
                raw = xobjects.get(key)
                if not isinstance(raw, pikepdf.Stream) or raw.objgen in seen:
                    continue
                seen.add(raw.objgen)
                label = f"page {index + 1} image {name}"
                prefix = directory / f"{source.stem}_p{index + 1}_{name.lstrip('/')}"
                image = pikepdf.PdfImage(raw)
                try:
                    written = image.extract_to(fileprefix=str(prefix))
                except (pikepdf.PikepdfError, NotImplementedError, OSError) as error:
                    warnings.append(f"Skipped {label}: {error}")
                    continue
                files.append(written)
                records.append(
                    {
                        "page": index + 1,
                        "name": name,
                        "file": written,
                        "width": image.width,
                        "height": image.height,
                    }
                )
    if not records:
        warnings.append("No extractable images were found on the selected pages.")
    return ToolOutcome(
        output_files=tuple(files),
        data={"image_count": len(records), "images": records},
        warnings=tuple(warnings),
    )


def pdf_render(
    input_file: InputFile,
    output_dir: OutputDir,
    pages: Pages = "1",
    dpi: Annotated[
        float, Field(gt=0, le=1200, description="Render resolution in dots per inch.")
    ] = 150,
    image_format: Annotated[
        RenderFormat, Field(description="Output image format: 'png' or 'jpeg'.")
    ] = RenderFormat.PNG,
    password: Password = None,
) -> ToolOutcome:
    source = input_path(input_file)
    directory = output_directory(output_dir)
    indexes = dict.fromkeys(parse_page_ranges(pages, page_count(source, password)))
    extension = "jpg" if image_format is RenderFormat.JPEG else "png"
    files: list[str] = []
    records: list[JsonValue] = []
    for index in indexes:
        picture = render_page(source, index, dpi, password)
        target = directory / f"{source.stem}_page{index + 1}.{extension}"
        if image_format is RenderFormat.JPEG:
            picture.convert("RGB").save(target, "JPEG", quality=JPEG_QUALITY)
        else:
            picture.save(target, "PNG")
        files.append(str(target))
        records.append(
            {
                "page": index + 1,
                "file": str(target),
                "width": picture.width,
                "height": picture.height,
            }
        )
    return ToolOutcome(
        output_files=tuple(files),
        data={"dpi": dpi, "format": image_format.value, "pages": records},
    )
