"""Sole pypdfium2 boundary: rendering, page text, and text search boxes.

Lanes call these helpers instead of importing pypdfium2, which ships no type stubs.
Coordinates are PDF points with the origin at the bottom-left of the page.
"""

from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Protocol, cast

import pypdfium2 as pdfium  # pyright: ignore[reportMissingTypeStubs]
from PIL import Image

from paddlepdf.pdftools.contract import PdfToolError

type Box = tuple[float, float, float, float]


class _Bitmap(Protocol):
    def to_pil(self) -> Image.Image: ...


class _RenderablePage(Protocol):
    def render(self, *, scale: float) -> _Bitmap: ...


def _renderable(page: object) -> _RenderablePage:
    return cast("_RenderablePage", page)


@contextmanager
def _document(path: Path, password: str | None) -> Generator[pdfium.PdfDocument]:
    try:
        document = pdfium.PdfDocument(path, password=password or None)
    except pdfium.PdfiumError as error:
        msg = f"Cannot open PDF {path}: {error}"
        raise PdfToolError(msg) from error
    try:
        yield document
    finally:
        document.close()


def page_count(path: Path, password: str | None = None) -> int:
    with _document(path, password) as document:
        return len(document)


def render_page(
    path: Path, page_index: int, dpi: float = 150, password: str | None = None
) -> Image.Image:
    with _document(path, password) as document:
        return _renderable(document[page_index]).render(scale=dpi / 72).to_pil().copy()


def page_texts(path: Path, password: str | None = None) -> list[str]:
    with _document(path, password) as document:
        texts: list[str] = []
        for page in document:
            text_page = page.get_textpage()
            texts.append(str(text_page.get_text_range()))
            text_page.close()
        return texts


def find_text_boxes(
    path: Path,
    needle: str,
    *,
    match_case: bool = False,
    whole_word: bool = False,
    password: str | None = None,
) -> dict[int, list[Box]]:
    """Map zero-based page index to the boxes covering each occurrence of ``needle``."""
    boxes: dict[int, list[Box]] = {}
    with _document(path, password) as document:
        for page_index, page in enumerate(document):
            text_page = page.get_textpage()
            searcher = text_page.search(
                needle, match_case=match_case, match_whole_word=whole_word
            )
            while hit := cast("tuple[int, int] | None", searcher.get_next()):
                rect_count = cast("int", text_page.count_rects(hit[0], hit[1]))
                for rect_index in range(rect_count):
                    box: Box = text_page.get_rect(rect_index)
                    boxes.setdefault(page_index, []).append(box)
            searcher.close()
            text_page.close()
    return boxes
