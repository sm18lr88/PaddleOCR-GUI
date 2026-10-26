"""pdf_overlay_underlay: stamp the first page of a template PDF behind or over pages."""

import base64
import binascii
import io
from enum import StrEnum
from pathlib import Path
from typing import Annotated

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
from paddlepdf.pdftools.layout.compose import (
    Placement,
    add_resource,
    import_page,
    paint_over,
    paint_under,
    place_ops,
)


class OverlayMode(StrEnum):
    UNDERLAY = "underlay"
    OVERLAY = "overlay"


def _open_template(
    template_file: str | None, template_data: str | None, password: str | None
) -> pikepdf.Pdf:
    if template_data:
        try:
            raw = base64.b64decode(template_data, validate=True)
            return pikepdf.open(io.BytesIO(raw), password=password or "")
        except (binascii.Error, pikepdf.PdfError) as error:
            msg = f"template_data is not a readable base64 PDF: {error}"
            raise PdfToolError(msg) from error
    if template_file:
        template_path: Path = input_path(template_file)
        return open_pdf(template_path, password)
    msg = "Provide template_file or template_data"
    raise PdfToolError(msg)


def pdf_overlay_underlay(
    input_file: Annotated[str, Field(description="Path to the PDF to modify.")],
    output_file: Annotated[str, Field(description="Path of the stamped PDF to write.")],
    template_file: Annotated[
        str | None,
        Field(description="Path to the template PDF (letterhead, watermark)."),
    ] = None,
    template_data: Annotated[
        str | None,
        Field(description="Base64 template PDF; used instead of template_file."),
    ] = None,
    mode: Annotated[
        OverlayMode,
        Field(description="underlay draws behind page content, overlay draws on top."),
    ] = OverlayMode.UNDERLAY,
    pages: Annotated[
        str,
        Field(description='Target pages, 1-based: "all", "first", "last", "1,3-5".'),
    ] = "all",
    opacity: Annotated[
        float, Field(ge=0, le=1, description="Template opacity from 0 to 1.")
    ] = 1.0,
    password: Annotated[
        str | None, Field(description="Password of the input PDF.")
    ] = None,
    template_password: Annotated[
        str | None, Field(description="Password of the template PDF.")
    ] = None,
) -> ToolOutcome:
    source_path = input_path(input_file)
    target = output_path(output_file, source_path)
    pdf = open_pdf(source_path, password)
    template = _open_template(template_file, template_data, template_password)
    if len(template.pages) == 0:
        msg = "Template PDF has no pages"
        raise PdfToolError(msg)
    spec = "1" if pages.strip().lower() == "first" else pages
    targets = sorted(set(parse_page_ranges(spec, len(pdf.pages))))
    form = import_page(pdf, template.pages[0])
    graphics_state = pdf.make_indirect(
        pikepdf.Dictionary(Type=pikepdf.Name.ExtGState, ca=opacity, CA=opacity)
    )
    for index in targets:
        page = pdf.pages[index]
        left, bottom, *_ = (float(value) for value in page.mediabox)
        stamp = place_ops("TplOverlay", Placement(form, 1.0, left, bottom))
        add_resource(page, "/XObject", "/TplOverlay", form.form)
        operations = stamp
        if opacity < 1.0:
            add_resource(page, "/ExtGState", "/TplOpacity", graphics_state)
            operations = b"/TplOpacity gs\n" + stamp
        if mode is OverlayMode.UNDERLAY:
            paint_under(pdf, page, operations)
        else:
            paint_over(pdf, page, operations)
    written = save_pdf(pdf, target)
    data: dict[str, JsonValue] = {
        "mode": mode.value,
        "stamped_pages": [i + 1 for i in targets],
    }
    return ToolOutcome(output_files=(written,), data=data)
