"""Document info and Info-dictionary/XMP metadata tools."""

from collections.abc import Mapping
from typing import Annotated, cast

import pikepdf
from pydantic import Field, JsonValue

from paddlepdf.pdftools.common import input_path, open_pdf, output_path, save_pdf
from paddlepdf.pdftools.contract import PdfToolError, ToolOutcome

_DOCINFO_FIELDS = {
    "title": "/Title",
    "author": "/Author",
    "subject": "/Subject",
    "keywords": "/Keywords",
}


def pdf_info(
    input_file: Annotated[str, Field(description="Input PDF path.")],
    password: Annotated[str | None, Field(description="Password if encrypted.")] = None,
) -> ToolOutcome:
    path = input_path(input_file)
    with open_pdf(path, password) as pdf:
        data: dict[str, JsonValue] = {
            "page_count": len(pdf.pages),
            "version": pdf.pdf_version,
            "encrypted": pdf.is_encrypted,
            "linearized": pdf.is_linearized,
            "file_size_bytes": path.stat().st_size,
        }
    return ToolOutcome(data=data)


def pdf_metadata(
    input_file: Annotated[str, Field(description="Input PDF path.")],
    output_file: Annotated[
        str | None,
        Field(description="Output PDF path; required when any field below is set."),
    ] = None,
    title: Annotated[str | None, Field(description="New Title.")] = None,
    author: Annotated[str | None, Field(description="New Author.")] = None,
    subject: Annotated[str | None, Field(description="New Subject.")] = None,
    keywords: Annotated[str | None, Field(description="New Keywords.")] = None,
    password: Annotated[str | None, Field(description="Password if encrypted.")] = None,
) -> ToolOutcome:
    path = input_path(input_file)
    updates = {
        key: value
        for key, value in {
            "title": title,
            "author": author,
            "subject": subject,
            "keywords": keywords,
        }.items()
        if value is not None
    }
    if updates and output_file is None:
        msg = "output_file is required to write metadata; omit the fields to read"
        raise PdfToolError(msg)
    destination = output_path(output_file, path) if output_file else None
    with open_pdf(path, password) as pdf:
        before = _read_docinfo(pdf)
        data: dict[str, JsonValue] = {"metadata": before}
        has_xmp = "/Metadata" in pdf.Root
        if has_xmp:
            data["xmp"] = _read_xmp(pdf)
        if destination is None:
            return ToolOutcome(data=data)
        for key, value in updates.items():
            pdf.docinfo[_DOCINFO_FIELDS[key]] = value
        if has_xmp and updates:
            _write_xmp(pdf, updates)
        data["updated"] = list[JsonValue](sorted(updates))
        data["metadata"] = _read_docinfo(pdf)
        return ToolOutcome(output_files=(save_pdf(pdf, destination),), data=data)


def _read_docinfo(pdf: pikepdf.Pdf) -> dict[str, JsonValue]:
    return {
        str(key).lstrip("/").lower(): str(value) for key, value in pdf.docinfo.items()
    }


def _as_mapping(value: object) -> Mapping[str, object]:
    return cast("Mapping[str, object]", value)


def _xmp_value(value: object) -> JsonValue:
    if isinstance(value, str):
        return value
    return [str(item) for item in cast("list[object]", value)]


def _read_xmp(pdf: pikepdf.Pdf) -> dict[str, JsonValue]:
    with pdf.open_metadata(set_pikepdf_as_editor=False, update_docinfo=False) as meta:
        return {str(key): _xmp_value(value) for key, value in _as_mapping(meta).items()}


def _write_xmp(pdf: pikepdf.Pdf, updates: dict[str, str]) -> None:
    with pdf.open_metadata(set_pikepdf_as_editor=False, update_docinfo=False) as meta:
        if "title" in updates:
            meta["dc:title"] = updates["title"]
        if "author" in updates:
            meta["dc:creator"] = [updates["author"]]
        if "subject" in updates:
            meta["dc:description"] = updates["subject"]
        if "keywords" in updates:
            meta["pdf:Keywords"] = updates["keywords"]
