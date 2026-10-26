"""Blank-page removal."""

from typing import Annotated

import pikepdf
from pydantic import Field

from paddlepdf.pdftools.common import input_path, open_pdf, output_path, save_pdf
from paddlepdf.pdftools.contract import PdfToolError, ToolOutcome
from paddlepdf.pdftools.pdfium import page_texts

MIN_BYTE_THRESHOLD = 500


def _has_xobjects(page: pikepdf.Page) -> bool:
    resources = page.obj.get("/Resources")
    if not isinstance(resources, pikepdf.Dictionary):
        return False
    xobjects = resources.get("/XObject")
    return isinstance(xobjects, pikepdf.Dictionary) and len(xobjects) > 0


def _content_length(page: pikepdf.Page) -> int:
    contents = page.obj.get("/Contents")
    if contents is None:
        return 0
    streams = list(contents) if isinstance(contents, pikepdf.Array) else [contents]
    return sum(
        len(stream.read_bytes())
        for stream in streams
        if isinstance(stream, pikepdf.Stream)
    )


def pdf_remove_blank(
    input_file: Annotated[str, Field(description="Input PDF path.")],
    output_file: Annotated[str, Field(description="Output PDF path.")],
    sensitivity: Annotated[
        int,
        Field(
            ge=0,
            le=100,
            description="0-100; higher treats more near-empty pages as blank.",
        ),
    ] = 95,
    password: Annotated[str | None, Field(description="PDF password.")] = None,
) -> ToolOutcome:
    """Drop pages with no text, no XObjects, and an almost empty content stream."""
    source = input_path(input_file)
    target = output_path(output_file, source)
    threshold = max(sensitivity * 3, MIN_BYTE_THRESHOLD)
    texts = page_texts(source, password)
    with open_pdf(source, password) as pdf:
        blank = [
            index
            for index, page in enumerate(pdf.pages)
            if not _has_xobjects(page)
            and not texts[index].strip()
            and _content_length(page) <= threshold
        ]
        if len(blank) == len(pdf.pages):
            msg = "Every page is blank; refusing to write an empty PDF"
            raise PdfToolError(msg)
        for index in reversed(blank):
            del pdf.pages[index]
        saved = save_pdf(pdf, target)
        remaining = len(pdf.pages)
    return ToolOutcome(
        output_files=(saved,),
        data={"removed_pages": [index + 1 for index in blank], "remaining": remaining},
    )
