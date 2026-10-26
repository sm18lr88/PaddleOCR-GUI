"""pdf_create_form_field: add a new text or checkbox widget to a PDF page."""

from collections.abc import Callable
from enum import StrEnum
from typing import Annotated, cast

import pikepdf
from pydantic import Field

from paddlepdf.pdftools.common import input_path, open_pdf, output_path, save_pdf
from paddlepdf.pdftools.contract import PdfToolError, ToolOutcome
from paddlepdf.pdftools.forms._appearance import (
    TEXT_DEFAULT_APPEARANCE,
    checkbox_appearances,
    ensure_helvetica_resource,
)


class CreatableFieldType(StrEnum):
    TEXT = "text"
    CHECKBOX = "checkbox"


def pdf_create_form_field(
    input_file: Annotated[str, Field(description="The input PDF file path.")],
    output_file: Annotated[str, Field(description="The output PDF file path.")],
    field_name: Annotated[str, Field(description="Name of the new form field.")],
    field_type: Annotated[
        CreatableFieldType, Field(description="Widget kind: 'text' or 'checkbox'.")
    ],
    page: Annotated[
        int, Field(description="1-based page number to place the field on.", ge=1)
    ],
    rect: Annotated[
        tuple[float, float, float, float],
        Field(
            description="Widget position as (left, bottom, right, top) in PDF points."
        ),
    ],
    password: Annotated[
        str | None, Field(description="Password for an encrypted PDF, if any.")
    ] = None,
) -> ToolOutcome:
    """Add a text or checkbox AcroForm widget to one page and save a new PDF."""
    source = input_path(input_file)
    destination = output_path(output_file, source)
    pdf = open_pdf(source, password)
    try:
        if page > len(pdf.pages):
            msg = f"Page {page} not found; the PDF has {len(pdf.pages)} pages"
            raise PdfToolError(msg)
        target_page = pdf.pages[page - 1]
        is_checkbox = field_type is CreatableFieldType.CHECKBOX
        widget = pdf.make_indirect(
            pikepdf.Dictionary(
                Type=pikepdf.Name.Annot,
                Subtype=pikepdf.Name.Widget,
                FT=pikepdf.Name.Btn if is_checkbox else pikepdf.Name.Tx,
                T=field_name,
                Rect=list(rect),
                V=pikepdf.Name("/Off") if is_checkbox else "",
            )
        )
        if is_checkbox:
            widget.AS = pikepdf.Name("/Off")
            left, bottom, right, top = rect
            widget.AP = checkbox_appearances(pdf, right - left, top - bottom)
        else:
            widget.DA = pikepdf.String(TEXT_DEFAULT_APPEARANCE)
        widget.P = target_page.obj
        if "/Annots" in target_page.obj:
            target_page.obj.Annots.append(widget)
        else:
            target_page.obj.Annots = pikepdf.Array([widget])
        make_field = cast(
            "Callable[[pikepdf.Object], pikepdf.AcroFormField]", pikepdf.AcroFormField
        )
        pdf.acroform.add_field(make_field(widget))
        ensure_helvetica_resource(pdf)
        written = save_pdf(pdf, destination)
    finally:
        pdf.close()
    return ToolOutcome(output_files=(written,))
