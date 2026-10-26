"""Tools that pick, drop, reorder, or rotate pages of one document."""

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
from paddlepdf.pdftools.pages_basic.pageset import build_pdf

_QUARTER_TURN = 90
_FULL_TURN = 360


def _require_pages(indexes: list[int]) -> None:
    if not indexes:
        msg = "No pages selected"
        raise PdfToolError(msg)


def pdf_extract_pages(
    input_file: Annotated[str, Field(description="Input PDF file.")],
    pages: Annotated[
        str, Field(description="1-based pages to keep, e.g. '1,3-5,last'.")
    ],
    output_file: Annotated[str, Field(description="Path of the PDF to write.")],
    password: Annotated[
        str | None, Field(description="Password of the input PDF.")
    ] = None,
) -> ToolOutcome:
    source = input_path(input_file)
    target = output_path(output_file, source)
    pdf = open_pdf(source, password)
    keep = sorted(set(parse_page_ranges(pages, len(pdf.pages))))
    _require_pages(keep)
    return ToolOutcome(
        output_files=(save_pdf(build_pdf(pdf, keep), target),),
        data={"page_count": len(keep)},
    )


def pdf_delete_pages(
    input_file: Annotated[str, Field(description="Input PDF file.")],
    pages: Annotated[
        str, Field(description="1-based pages to delete, e.g. '2,4-6,last'.")
    ],
    output_file: Annotated[str, Field(description="Path of the PDF to write.")],
    password: Annotated[
        str | None, Field(description="Password of the input PDF.")
    ] = None,
) -> ToolOutcome:
    source = input_path(input_file)
    target = output_path(output_file, source)
    pdf = open_pdf(source, password)
    count = len(pdf.pages)
    drop = set(parse_page_ranges(pages, count))
    _require_pages(sorted(drop))
    keep = [index for index in range(count) if index not in drop]
    if not keep:
        msg = "Refusing to delete every page of the document"
        raise PdfToolError(msg)
    return ToolOutcome(
        output_files=(save_pdf(build_pdf(pdf, keep), target),),
        data={"page_count": len(keep), "deleted": len(drop)},
    )


def pdf_reorder_pages(
    input_file: Annotated[str, Field(description="Input PDF file.")],
    order: Annotated[
        str,
        Field(description="Complete new page order, 1-based, e.g. '3,1,2'; each once."),
    ],
    output_file: Annotated[str, Field(description="Path of the PDF to write.")],
    password: Annotated[
        str | None, Field(description="Password of the input PDF.")
    ] = None,
) -> ToolOutcome:
    source = input_path(input_file)
    target = output_path(output_file, source)
    pdf = open_pdf(source, password)
    count = len(pdf.pages)
    new_order = parse_page_ranges(order, count)
    if len(new_order) != count:
        msg = f"New order length ({len(new_order)}) must equal page count ({count})"
        raise PdfToolError(msg)
    if len(set(new_order)) != count:
        msg = "New order lists a page more than once"
        raise PdfToolError(msg)
    return ToolOutcome(
        output_files=(save_pdf(build_pdf(pdf, new_order), target),),
        data={"page_count": count, "order": [index + 1 for index in new_order]},
    )


def _current_rotation(page: pikepdf.Page) -> int:
    node: pikepdf.Object | None = page.obj
    while node is not None:
        if "/Rotate" in node:
            return int(node["/Rotate"])
        node = node.get("/Parent")
    return 0


def pdf_rotate(
    input_file: Annotated[str, Field(description="Input PDF file.")],
    angle: Annotated[
        int,
        Field(
            description="Clockwise degrees added to current rotation; multiple of 90."
        ),
    ],
    output_file: Annotated[str, Field(description="Path of the PDF to write.")],
    pages: Annotated[
        str,
        Field(
            description="1-based pages to rotate, e.g. '1,3-5'; 'all' for every page."
        ),
    ] = "all",
    password: Annotated[
        str | None, Field(description="Password of the input PDF.")
    ] = None,
) -> ToolOutcome:
    if angle % _QUARTER_TURN != 0:
        msg = "Rotation must be a multiple of 90 degrees"
        raise PdfToolError(msg)
    source = input_path(input_file)
    target = output_path(output_file, source)
    pdf = open_pdf(source, password)
    indexes = sorted(set(parse_page_ranges(pages, len(pdf.pages))))
    rotations: dict[str, JsonValue] = {}
    for index in indexes:
        page = pdf.pages[index]
        total = (_current_rotation(page) + angle) % _FULL_TURN
        page.obj["/Rotate"] = total
        rotations[str(index + 1)] = total
    return ToolOutcome(
        output_files=(save_pdf(pdf, target),), data={"rotations": rotations}
    )
