"""office_to_markdown, office_extract_text, and office_modernize_legacy."""

import shutil
from pathlib import Path
from typing import Annotated, Final

from pydantic import Field

from paddlepdf.pdftools.common import input_path, output_path
from paddlepdf.pdftools.contract import PdfToolError, ToolOutcome
from paddlepdf.pdftools.office.blocks import read_blocks, to_markdown, to_text
from paddlepdf.pdftools.office.formats import (
    LEGACY_SUFFIXES,
    OfficeFamily,
    detect_family,
    open_docx,
    open_pptx,
    open_xlsx,
)

OFFICE_SUFFIXES: Final = (".docx", ".pptx", ".xlsx", ".xlsm", *LEGACY_SUFFIXES)
_LEGACY_TARGET: Final[dict[str, OfficeFamily]] = {
    ".doc": "docx",
    ".xls": "xlsx",
    ".ppt": "pptx",
}


def _convert(input_file: str, output_file: str, *, markdown: bool) -> ToolOutcome:
    source = input_path(input_file, OFFICE_SUFFIXES)
    target = output_path(output_file, source)
    family = detect_family(source)
    blocks = read_blocks(source, family)
    content = to_markdown(blocks) if markdown else to_text(blocks)
    target.write_text(content, encoding="utf-8")
    warnings = () if blocks else (f"No text content found in {source.name}",)
    return ToolOutcome(
        output_files=(str(target),),
        data={"format": family, "blocks": len(blocks), "characters": len(content)},
        warnings=warnings,
    )


def office_to_markdown(
    input_file: Annotated[
        str, Field(description="Word, PowerPoint, or Excel file (.docx/.pptx/.xlsx).")
    ],
    output_file: Annotated[str, Field(description="Destination .md path.")],
) -> ToolOutcome:
    return _convert(input_file, output_file, markdown=True)


def office_extract_text(
    input_file: Annotated[
        str, Field(description="Word, PowerPoint, or Excel file (.docx/.pptx/.xlsx).")
    ],
    output_file: Annotated[str, Field(description="Destination .txt path.")],
) -> ToolOutcome:
    return _convert(input_file, output_file, markdown=False)


def _validate_package(path: Path, family: OfficeFamily) -> None:
    match family:
        case "docx":
            open_docx(path)
        case "pptx":
            open_pptx(path)
        case "xlsx":
            open_xlsx(path).close()


def office_modernize_legacy(
    input_file: Annotated[
        str,
        Field(description="Legacy-named Office file (.doc/.xls/.ppt) or OOXML file."),
    ],
    output_file: Annotated[
        str,
        Field(description="Destination with the modern suffix (.docx/.xlsx/.pptx)."),
    ],
) -> ToolOutcome:
    source = input_path(input_file, (*LEGACY_SUFFIXES, ".docx", ".xlsx", ".pptx"))
    target = output_path(output_file, source)
    family = detect_family(source)
    expected = _LEGACY_TARGET.get(source.suffix.lower(), family)
    if family != expected:
        msg = f"{source.name} holds a {family} package, not the {expected} it names"
        raise PdfToolError(msg)
    if target.suffix.lower() != f".{family}":
        msg = f"{source.name} is a {family} document; output_file must end in .{family}"
        raise PdfToolError(msg)
    _validate_package(source, family)
    shutil.copyfile(source, target)
    return ToolOutcome(
        output_files=(str(target),),
        data={"format": family, "source_container": "ooxml"},
        warnings=(f"{source.name} already holds Office Open XML; copied as .{family}",),
    )
