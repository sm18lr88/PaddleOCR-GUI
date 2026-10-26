"""Shared pikepdf page-selection helpers for the basic page tools."""

from collections.abc import Iterable
from pathlib import Path

import pikepdf

from paddlepdf.pdftools.common import output_path, save_pdf


def build_pdf(source: pikepdf.Pdf, indexes: Iterable[int]) -> pikepdf.Pdf:
    """Copy the given zero-based pages of ``source`` into a new document, in order."""
    target = pikepdf.new()
    for index in indexes:
        target.pages.append(source.pages[index])
    return target


def write_parts(
    source: pikepdf.Pdf,
    source_path: Path,
    output_dir: Path,
    parts: list[list[int]],
) -> tuple[str, ...]:
    """Save each page group as ``<stem>-<n>.pdf`` (n from 1) in ``output_dir``."""
    written: list[str] = []
    for number, indexes in enumerate(parts, start=1):
        target = output_path(
            str(output_dir / f"{source_path.stem}-{number}.pdf"), source_path
        )
        written.append(save_pdf(build_pdf(source, indexes), target))
    return tuple(written)
