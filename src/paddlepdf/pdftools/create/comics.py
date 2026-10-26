"""pdf_comic_archive: PDF -> CBZ of rendered pages, and CBZ/CBT -> PDF."""

import re
import tarfile
import zipfile
from io import BytesIO
from pathlib import Path, PurePosixPath
from typing import Annotated, Final, Literal

from pydantic import Field, JsonValue
from reportlab.pdfgen.canvas import Canvas

from paddlepdf.pdftools.common import input_path, output_path, parse_page_ranges
from paddlepdf.pdftools.contract import PdfToolError, ToolOutcome
from paddlepdf.pdftools.create.imaging import (
    IMAGE_SUFFIXES,
    draw_image_page,
    prepare_image,
)
from paddlepdf.pdftools.pdfium import page_count, render_page

_ZIP_ARCHIVES: Final = (".cbz", ".zip")
_TAR_ARCHIVES: Final = (".cbt", ".tar")
_UNSUPPORTED: Final = {
    ".cbr": "CBR (RAR)",
    ".rar": "RAR",
    ".cb7": "CB7 (7-Zip)",
    ".7z": "7-Zip",
}
_ACCEPTED: Final = (".pdf", *_ZIP_ARCHIVES, *_TAR_ARCHIVES, *_UNSUPPORTED)
_DIGITS: Final = re.compile(r"(\d+)")


def _natural_key(name: str) -> tuple[tuple[int, int, str], ...]:
    return tuple(
        (1, int(token), "") if token.isdigit() else (0, 0, token)
        for token in _DIGITS.split(name.lower())
    )


def _is_page_image(name: str) -> bool:
    path = PurePosixPath(name.replace("\\", "/"))
    hidden = path.name.startswith(".") or "__MACOSX" in path.parts
    return not hidden and path.suffix.lower() in IMAGE_SUFFIXES


def _archive_images(source: Path) -> list[tuple[str, bytes]]:
    suffix = source.suffix.lower()
    try:
        if suffix in _ZIP_ARCHIVES:
            with zipfile.ZipFile(source) as archive:
                names = [
                    info.filename
                    for info in archive.infolist()
                    if not info.is_dir() and _is_page_image(info.filename)
                ]
                return [
                    (name, archive.read(name))
                    for name in sorted(names, key=_natural_key)
                ]
        with tarfile.open(source) as archive:
            members = [
                member
                for member in archive.getmembers()
                if member.isfile() and _is_page_image(member.name)
            ]
            images: list[tuple[str, bytes]] = []
            for member in sorted(members, key=lambda item: _natural_key(item.name)):
                handle = archive.extractfile(member)
                if handle is not None:
                    images.append((member.name, handle.read()))
            return images
    except (zipfile.BadZipFile, tarfile.TarError) as error:
        msg = f"Cannot read comic archive {source}: {error}"
        raise PdfToolError(msg) from error


def _archive_to_pdf(source: Path, target: Path) -> ToolOutcome:
    if target.suffix.lower() != ".pdf":
        msg = f"Converting {source.suffix} needs a .pdf output_file, got {target.name}"
        raise PdfToolError(msg)
    entries = _archive_images(source)
    if not entries:
        msg = f"No page images ({', '.join(IMAGE_SUFFIXES)}) found in {source}"
        raise PdfToolError(msg)
    canvas = Canvas(str(target))
    for name, data in entries:
        draw_image_page(canvas, prepare_image(data, f"{source.name}:{name}"))
    canvas.save()
    return ToolOutcome(
        output_files=(str(target),),
        data={
            "direction": "archive_to_pdf",
            "page_count": len(entries),
            "pages": [name for name, _ in entries],
        },
    )


def _pdf_to_archive(
    source: Path,
    target: Path,
    pages: str,
    dpi: float,
    image_format: Literal["jpeg", "png"],
    jpeg_quality: int,
    password: str | None,
) -> ToolOutcome:
    if target.suffix.lower() not in _ZIP_ARCHIVES:
        msg = (
            f"PDF input converts to a .cbz archive; got {target.name}. "
            "CBR (RAR) cannot be written: RAR compression is proprietary."
        )
        raise PdfToolError(msg)
    indexes = parse_page_ranges(pages, page_count(source, password))
    width = max(3, len(str(len(indexes))))
    extension = "jpg" if image_format == "jpeg" else "png"
    names: list[str] = []
    with zipfile.ZipFile(target, "w") as archive:
        for number, index in enumerate(indexes, start=1):
            image = render_page(source, index, dpi, password)
            buffer = BytesIO()
            if image_format == "jpeg":
                image.convert("RGB").save(buffer, "JPEG", quality=jpeg_quality)
                compression = zipfile.ZIP_STORED
            else:
                image.save(buffer, "PNG")
                compression = zipfile.ZIP_DEFLATED
            name = f"page-{number:0{width}d}.{extension}"
            archive.writestr(name, buffer.getvalue(), compress_type=compression)
            names.append(name)
    return ToolOutcome(
        output_files=(str(target),),
        data={
            "direction": "pdf_to_archive",
            "page_count": len(names),
            "pages": list[JsonValue](names),
        },
    )


def pdf_comic_archive(
    input_file: Annotated[
        str,
        Field(description="A .pdf (rendered to CBZ) or a .cbz/.zip/.cbt/.tar archive."),
    ],
    output_file: Annotated[
        str, Field(description="Target: .cbz for PDF input, .pdf for archive input.")
    ],
    pages: Annotated[
        str,
        Field(description="PDF pages to archive, 1-based like '1,3-5,last' or 'all'."),
    ] = "all",
    dpi: Annotated[
        float, Field(ge=36, le=600, description="Render resolution for PDF -> CBZ.")
    ] = 150,
    image_format: Annotated[
        Literal["jpeg", "png"], Field(description="Page image format inside the CBZ.")
    ] = "jpeg",
    jpeg_quality: Annotated[
        int, Field(ge=1, le=100, description="JPEG quality for PDF -> CBZ.")
    ] = 90,
    password: Annotated[
        str | None, Field(description="Password of the input PDF.")
    ] = None,
) -> ToolOutcome:
    source = input_path(input_file, _ACCEPTED)
    suffix = source.suffix.lower()
    if suffix in _UNSUPPORTED:
        kind = _UNSUPPORTED[suffix]
        hint = "re-pack the images as a .cbz (zip) and retry"
        msg = f"{kind} archives are not supported (no pure-Python decoder); {hint}."
        raise PdfToolError(msg)
    target = output_path(output_file, source)
    if suffix == ".pdf":
        return _pdf_to_archive(
            source, target, pages, dpi, image_format, jpeg_quality, password
        )
    return _archive_to_pdf(source, target)
