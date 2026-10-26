"""Embedded-file listing, adding, extracting, and removing."""

import base64
import binascii
import json
from enum import StrEnum
from pathlib import Path
from typing import Annotated

import pikepdf
from pydantic import Field, JsonValue

from paddlepdf.pdftools.common import input_path, open_pdf, output_path, save_pdf
from paddlepdf.pdftools.contract import PdfToolError, ToolOutcome


class AttachmentAction(StrEnum):
    LIST = "list"
    ADD = "add"
    EXTRACT = "extract"
    REMOVE = "remove"


def pdf_attachments(
    input_file: Annotated[str, Field(description="Input PDF path.")],
    action: Annotated[
        AttachmentAction, Field(description="list, add, extract, or remove.")
    ] = AttachmentAction.LIST,
    output_file: Annotated[
        str | None,
        Field(
            description=(
                "add/remove: output PDF. extract: path for the extracted bytes. "
                "list: optional JSON report."
            )
        ),
    ] = None,
    file_name: Annotated[
        str | None, Field(description="Attachment name (add/extract/remove).")
    ] = None,
    description: Annotated[
        str | None, Field(description="Description for add.")
    ] = None,
    mime_type: Annotated[
        str | None, Field(description="MIME type for add, e.g. text/plain.")
    ] = None,
    file_data_base64: Annotated[
        str | None, Field(description="Base64 content for add.")
    ] = None,
    source_file: Annotated[
        str | None,
        Field(
            description="Local file to embed for add (alternative to file_data_base64)."
        ),
    ] = None,
    password: Annotated[str | None, Field(description="Password if encrypted.")] = None,
) -> ToolOutcome:
    path = input_path(input_file)
    with open_pdf(path, password) as pdf:
        if action is AttachmentAction.LIST:
            return _list(pdf, output_file, path)
        if output_file is None:
            msg = f"output_file is required for action {action.value!r}"
            raise PdfToolError(msg)
        destination = output_path(output_file, path)
        if action is AttachmentAction.ADD:
            name = _add(
                pdf, file_name, description, mime_type, file_data_base64, source_file
            )
            return ToolOutcome(
                output_files=(save_pdf(pdf, destination),), data={"added": name}
            )
        name = _require_existing(pdf, file_name)
        if action is AttachmentAction.EXTRACT:
            content = pdf.attachments[name].get_file().read_bytes()
            destination.write_bytes(content)
            return ToolOutcome(
                output_files=(str(destination),),
                data={"name": name, "size_bytes": len(content)},
            )
        del pdf.attachments[name]
        return ToolOutcome(
            output_files=(save_pdf(pdf, destination),), data={"removed": name}
        )


def _list(pdf: pikepdf.Pdf, output_file: str | None, source: Path) -> ToolOutcome:
    attachments: list[JsonValue] = []
    for name, spec in pdf.attachments.items():
        attached = spec.get_file()
        attachments.append(
            {
                "name": name,
                "size_bytes": len(attached.read_bytes()),
                "mime_type": attached.mime_type,
                "description": spec.description or None,
            }
        )
    data: dict[str, JsonValue] = {
        "attachments": attachments,
        "total_count": len(attachments),
    }
    if output_file is None:
        return ToolOutcome(data=data)
    report = output_path(output_file, source)
    report.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return ToolOutcome(output_files=(str(report),), data=data)


def _require_existing(pdf: pikepdf.Pdf, file_name: str | None) -> str:
    if not file_name:
        msg = "file_name is required for this action"
        raise PdfToolError(msg)
    if file_name not in pdf.attachments:
        msg = f"Attachment not found: {file_name}"
        raise PdfToolError(msg)
    return file_name


def _add(
    pdf: pikepdf.Pdf,
    file_name: str | None,
    description: str | None,
    mime_type: str | None,
    file_data_base64: str | None,
    source_file: str | None,
) -> str:
    if (file_data_base64 is None) == (source_file is None):
        msg = "Provide exactly one of file_data_base64 or source_file for add"
        raise PdfToolError(msg)
    if source_file is not None:
        source = input_path(source_file, suffixes=())
        content = source.read_bytes()
        name = file_name or source.name
    else:
        if not file_name:
            msg = "file_name is required when adding from file_data_base64"
            raise PdfToolError(msg)
        try:
            content = base64.b64decode((file_data_base64 or "").strip(), validate=True)
        except binascii.Error as error:
            msg = f"file_data_base64 is not valid base64: {error}"
            raise PdfToolError(msg) from error
        name = file_name
    pdf.attachments[name] = pikepdf.AttachedFileSpec(
        pdf,
        content,
        description=description or "",
        filename=name,
        mime_type=mime_type or "",
        creation_date="",
        mod_date="",
    )
    return name
