"""Path, page-range, and pikepdf open/save helpers shared by every tool lane."""

import re
from pathlib import Path
from typing import Final

import pikepdf

from paddlepdf.pdftools.contract import PdfToolError
from paddlepdf.user_paths import user_path

_RANGE_PART: Final = re.compile(r"^\s*(\d+|last)\s*(?:-\s*(\d+|last)\s*)?$")


def input_path(value: str, suffixes: tuple[str, ...] = (".pdf",)) -> Path:
    path = user_path(value)
    if not path.is_file():
        msg = f"Input file not found: {path}"
        raise PdfToolError(msg)
    if suffixes and path.suffix.lower() not in suffixes:
        msg = f"Unsupported input type {path.suffix!r} for {path}; expected {suffixes}"
        raise PdfToolError(msg)
    return path


def output_path(value: str, *inputs: Path) -> Path:
    path = user_path(value)
    if any(path == source for source in inputs):
        msg = f"Output must differ from input: {path}"
        raise PdfToolError(msg)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def output_directory(value: str) -> Path:
    path = user_path(value)
    path.mkdir(parents=True, exist_ok=True)
    return path


def parse_page_ranges(spec: str, page_count: int) -> list[int]:
    """Return zero-based page indexes for a 1-based spec like ``"1,3-5,last"``.

    Order and duplicates are preserved. ``"all"`` or an empty spec selects every
    page. Raises ``PdfToolError`` for malformed parts or pages outside the document.
    """
    cleaned = spec.strip().lower()
    if cleaned in {"", "all"}:
        return list(range(page_count))
    indexes: list[int] = []
    for part in cleaned.split(","):
        match = _RANGE_PART.match(part)
        if match is None:
            msg = f"Invalid page range {part.strip()!r}; use forms like 1,3-5,last"
            raise PdfToolError(msg)
        start = _page_number(match.group(1), page_count)
        end = _page_number(match.group(2) or match.group(1), page_count)
        step = 1 if end >= start else -1
        indexes.extend(number - 1 for number in range(start, end + step, step))
    return indexes


def _page_number(part: str, page_count: int) -> int:
    number = page_count if part == "last" else int(part)
    if not 1 <= number <= page_count:
        msg = f"Page {number} is outside the document (1-{page_count})"
        raise PdfToolError(msg)
    return number


def open_pdf(path: Path, password: str | None = None) -> pikepdf.Pdf:
    try:
        return pikepdf.open(path, password=password or "")
    except pikepdf.PasswordError as error:
        msg = f"Wrong or missing password for {path}"
        raise PdfToolError(msg) from error
    except pikepdf.PdfError as error:
        msg = f"Cannot read PDF {path}: {error}"
        raise PdfToolError(msg) from error


def save_pdf(pdf: pikepdf.Pdf, path: Path) -> str:
    pdf.save(path)
    return str(path)
