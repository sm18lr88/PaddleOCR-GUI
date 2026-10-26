"""Outline (bookmark) listing and editing."""

from enum import StrEnum
from typing import Annotated

import pikepdf
from pydantic import BaseModel, Field, JsonValue

from paddlepdf.pdftools.common import input_path, open_pdf, output_path, save_pdf
from paddlepdf.pdftools.contract import PdfToolError, ToolOutcome
from paddlepdf.pdftools.destinations import PageNumbers, outline_page, page_numbers


class BookmarkAction(StrEnum):
    LIST = "list"
    SET = "set"
    ADD = "add"
    CLEAR = "clear"


class BookmarkItem(BaseModel):
    title: str = Field(description="Bookmark label.")
    page: int = Field(ge=1, description="1-based destination page.")
    children: list["BookmarkItem"] = Field(
        default_factory=list, description="Nested bookmarks."
    )


def pdf_bookmarks(
    input_file: Annotated[str, Field(description="Input PDF path.")],
    action: Annotated[
        BookmarkAction,
        Field(
            description=(
                "list reads the outline; set replaces it; add appends; "
                "clear removes it."
            )
        ),
    ] = BookmarkAction.LIST,
    bookmarks: Annotated[
        list[BookmarkItem] | None,
        Field(description="Bookmarks for set/add: [{title, page, children}]."),
    ] = None,
    output_file: Annotated[
        str | None, Field(description="Output PDF; required for set/add/clear.")
    ] = None,
    password: Annotated[str | None, Field(description="Password if encrypted.")] = None,
) -> ToolOutcome:
    path = input_path(input_file)
    with open_pdf(path, password) as pdf:
        if action is BookmarkAction.LIST:
            return ToolOutcome(data={"bookmarks": _list(pdf)})
        if output_file is None:
            msg = f"output_file is required for action {action.value!r}"
            raise PdfToolError(msg)
        destination = output_path(output_file, path)
        items = bookmarks or []
        if action is not BookmarkAction.CLEAR and not items:
            msg = f"action {action.value!r} needs a non-empty bookmarks list"
            raise PdfToolError(msg)
        _check_pages(items, len(pdf.pages))
        with pdf.open_outline() as outline:
            if action is not BookmarkAction.ADD:
                outline.root.clear()
            outline.root.extend(_build(item) for item in items)
        return ToolOutcome(
            output_files=(save_pdf(pdf, destination),), data={"bookmarks": _list(pdf)}
        )


def _check_pages(items: list[BookmarkItem], page_count: int) -> None:
    for item in items:
        if item.page > page_count:
            msg = (
                f"Bookmark {item.title!r} targets page {item.page}; "
                f"document has {page_count}"
            )
            raise PdfToolError(msg)
        _check_pages(item.children, page_count)


def _build(item: BookmarkItem) -> pikepdf.OutlineItem:
    node = pikepdf.OutlineItem(item.title, item.page - 1)
    node.children.extend(_build(child) for child in item.children)
    return node


def _list(pdf: pikepdf.Pdf) -> list[JsonValue]:
    numbers = page_numbers(pdf)
    with pdf.open_outline() as outline:
        return [_describe(pdf, item, numbers) for item in outline.root]


def _describe(
    pdf: pikepdf.Pdf, item: pikepdf.OutlineItem, numbers: PageNumbers
) -> dict[str, JsonValue]:
    return {
        "title": str(item.title),
        "page": outline_page(pdf, item, numbers),
        "children": [_describe(pdf, child, numbers) for child in item.children],
    }
