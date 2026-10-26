"""Splitting tools: by outline into chapter files, and scanned two-up spreads."""

import re
import zipfile
from dataclasses import dataclass
from enum import StrEnum
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
from paddlepdf.pdftools.destinations import PageNumbers, outline_page, page_numbers
from paddlepdf.pdftools.pages_geometry.geometry import media_box

_UNSAFE_NAME = re.compile(r"[^\w \-]")


class ReadingDirection(StrEnum):
    LTR = "ltr"
    RTL = "rtl"


@dataclass(slots=True)
class Section:
    title: str
    start: int
    end: int = 0


def _collect(
    pdf: pikepdf.Pdf,
    items: list[pikepdf.OutlineItem],
    depth: int,
    max_depth: int,
    numbers: PageNumbers,
    sections: list[Section],
) -> None:
    for item in items:
        page = outline_page(pdf, item, numbers)
        title = str(item.title or "").strip()
        if page is not None and title:
            sections.append(Section(title, page))
        if depth < max_depth:
            _collect(pdf, list(item.children), depth + 1, max_depth, numbers, sections)


def pdf_split_by_outline(
    input_file: Annotated[str, Field(description="Input PDF path with bookmarks.")],
    output_dir: Annotated[str, Field(description="Directory for chapter PDFs.")],
    max_depth: Annotated[
        int, Field(ge=1, description="Bookmark depth to split at (1 = top level).")
    ] = 1,
    sanitize_names: Annotated[
        bool, Field(description="Replace unsafe filename characters with '_'.")
    ] = True,
    create_zip: Annotated[
        bool, Field(description="Also write chapters.zip with all chapter PDFs.")
    ] = False,
    password: Annotated[str | None, Field(description="PDF password.")] = None,
) -> ToolOutcome:
    """Write one numbered PDF per bookmark section (NN_Title.pdf) into output_dir."""
    source = input_path(input_file)
    folder = output_directory(output_dir)
    with open_pdf(source, password) as pdf:
        sections: list[Section] = []
        with pdf.open_outline() as outline:
            _collect(pdf, list(outline.root), 1, max_depth, page_numbers(pdf), sections)
        if not sections:
            msg = "No bookmarks with page destinations found"
            raise PdfToolError(msg)
        sections.sort(key=lambda section: section.start)
        total = len(pdf.pages)
        for position, section in enumerate(sections):
            following = (
                sections[position + 1].start
                if position + 1 < len(sections)
                else total + 1
            )
            section.end = max(section.start, following - 1)
        written: list[str] = []
        for position, section in enumerate(sections, start=1):
            name = (
                _UNSAFE_NAME.sub("_", section.title)
                if sanitize_names
                else section.title
            )
            name = name.replace("  ", " ").strip() or f"Chapter_{position}"
            part = pikepdf.Pdf.new()
            part.pages.extend(pdf.pages[section.start - 1 : section.end])
            written.append(save_pdf(part, folder / f"{position:02d}_{name}.pdf"))
    if create_zip:
        archive = folder / "chapters.zip"
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_STORED) as bundle:
            for file in written:
                bundle.write(file, arcname=file.rsplit("\\", 1)[-1].rsplit("/", 1)[-1])
        written.append(str(archive))
    return ToolOutcome(
        output_files=tuple(written),
        data=[
            {"title": s.title, "start_page": s.start, "end_page": s.end}
            for s in sections
        ],
    )


def _halves(
    box: tuple[float, float, float, float], gutter: float, *, horizontal: bool
) -> tuple[list[float], list[float]]:
    x0, y0, x1, y1 = box
    if horizontal:
        mid = (y0 + y1) / 2
        return [x0, y0, x1, mid + gutter], [x0, mid - gutter, x1, y1]
    mid = (x0 + x1) / 2
    return [x0, y0, mid + gutter, y1], [mid - gutter, y0, x1, y1]


def pdf_split_scanned_book(
    input_file: Annotated[str, Field(description="Input PDF of two-up scans.")],
    output_file: Annotated[str, Field(description="Output PDF path.")],
    reading_direction: Annotated[
        ReadingDirection, Field(description="ltr or rtl page order of the book.")
    ] = ReadingDirection.LTR,
    gutter_overlap: Annotated[
        float, Field(ge=0, description="Points each half extends past the centre line.")
    ] = 0.0,
    split_horizontal: Annotated[
        bool, Field(description="Split top/bottom instead of left/right.")
    ] = False,
    password: Annotated[str | None, Field(description="PDF password.")] = None,
) -> ToolOutcome:
    """Split every page at its midpoint into two pages ordered by reading direction."""
    source = input_path(input_file)
    target = output_path(output_file, source)
    with open_pdf(source, password) as pdf:
        originals = list(pdf.pages)
        ordered: list[pikepdf.Dictionary] = []
        for page in originals:
            first, second = _halves(
                media_box(page), gutter_overlap, horizontal=split_horizontal
            )
            # first = left/bottom half, second = right/top half.
            order = [first, second]
            if split_horizontal != (reading_direction == ReadingDirection.RTL):
                order.reverse()
            for area in order:
                copy = pdf.make_indirect(pikepdf.Dictionary(dict(page.obj.items())))
                copy["/MediaBox"] = pikepdf.Array(area)
                copy["/CropBox"] = pikepdf.Array(area)
                ordered.append(copy)
        del pdf.pages[:]
        for page_dict in ordered:
            pdf.pages.append(pikepdf.Page(page_dict))
        saved = save_pdf(pdf, target)
    return ToolOutcome(
        output_files=(saved,),
        data={"input_pages": len(originals), "output_pages": len(ordered)},
    )
