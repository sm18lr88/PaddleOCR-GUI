"""Tools that combine or break up whole documents: merge, split, burst."""

from itertools import pairwise
from typing import Annotated

import pikepdf
from pydantic import Field

from paddlepdf.pdftools.common import (
    input_path,
    open_pdf,
    output_directory,
    output_path,
    save_pdf,
)
from paddlepdf.pdftools.contract import PdfToolError, ToolOutcome
from paddlepdf.pdftools.pages_basic.pageset import write_parts

_MIN_MERGE_INPUTS = 2


def pdf_merge(
    input_files: Annotated[
        list[str],
        Field(description="PDF files to merge, in output order (at least 2)."),
    ],
    output_file: Annotated[str, Field(description="Path of the merged PDF to write.")],
) -> ToolOutcome:
    if len(input_files) < _MIN_MERGE_INPUTS:
        msg = "pdf_merge needs at least 2 input files"
        raise PdfToolError(msg)
    sources = [input_path(value) for value in input_files]
    target = output_path(output_file, *sources)
    merged = pikepdf.new()
    page_total = 0
    for source in sources:
        pdf = open_pdf(source)
        merged.pages.extend(pdf.pages)
        page_total += len(pdf.pages)
    return ToolOutcome(
        output_files=(save_pdf(merged, target),),
        data={"page_count": page_total, "merged_files": len(sources)},
    )


def _cut_points(spec: str, every: int | None, page_count: int) -> list[int]:
    """Return sorted 1-based pages after which a new part starts."""
    if every is not None:
        return list(range(every, page_count, every))
    if not spec.strip():
        return list(range(1, page_count))
    cuts: set[int] = set()
    for part in spec.split(","):
        end = part.strip().rsplit("-", 1)[-1].strip().lower()
        number = page_count if end == "last" else int(end) if end.isdigit() else 0
        if number == 0:
            msg = f"Invalid split point {part.strip()!r}; use forms like 3,6 or 1-3,4-6"
            raise PdfToolError(msg)
        if number < page_count:
            cuts.add(number)
    if not cuts:
        msg = f"No split point is inside the document (1-{page_count - 1})"
        raise PdfToolError(msg)
    return sorted(cuts)


def pdf_split(
    input_file: Annotated[str, Field(description="PDF file to split.")],
    output_dir: Annotated[
        str,
        Field(
            description="Directory for the parts, named <stem>-1.pdf, <stem>-2.pdf, ..."
        ),
    ],
    every: Annotated[
        int | None,
        Field(
            ge=1,
            description="Split into parts of this many pages. Wins over split_after.",
        ),
    ] = None,
    split_after: Annotated[
        str,
        Field(description="Pages after which a new part starts: '3,6' or '1-3,4-6'."),
    ] = "",
    password: Annotated[
        str | None, Field(description="Password of the input PDF.")
    ] = None,
) -> ToolOutcome:
    source = input_path(input_file)
    pdf = open_pdf(source, password)
    count = len(pdf.pages)
    cuts = _cut_points(split_after, every, count)
    bounds = [0, *cuts, count]
    parts = [list(range(low, high)) for low, high in pairwise(bounds)]
    files = write_parts(pdf, source, output_directory(output_dir), parts)
    return ToolOutcome(
        output_files=files,
        data={
            "parts": [
                {"file": f, "pages": len(p)} for f, p in zip(files, parts, strict=True)
            ]
        },
    )


def pdf_burst(
    input_file: Annotated[
        str, Field(description="PDF file to burst into single pages.")
    ],
    output_dir: Annotated[
        str,
        Field(description="Directory for single-page PDFs named <stem>-N.pdf"),
    ],
    password: Annotated[
        str | None, Field(description="Password of the input PDF.")
    ] = None,
) -> ToolOutcome:
    source = input_path(input_file)
    pdf = open_pdf(source, password)
    parts = [[index] for index in range(len(pdf.pages))]
    files = write_parts(pdf, source, output_directory(output_dir), parts)
    return ToolOutcome(output_files=files, data={"page_count": len(files)})
