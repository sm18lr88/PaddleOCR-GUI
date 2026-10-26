"""pdf_fill_form: set AcroForm field values and regenerate their appearances."""

from typing import Annotated

import pikepdf
from pydantic import Field

from paddlepdf.pdftools.common import input_path, open_pdf, output_path, save_pdf
from paddlepdf.pdftools.contract import PdfToolError, ToolOutcome
from paddlepdf.pdftools.forms._fields import (
    FieldKind,
    checkbox_on_state,
    field_kind,
    find_field,
)


def pdf_fill_form(
    input_file: Annotated[str, Field(description="The input PDF file path.")],
    output_file: Annotated[str, Field(description="The output PDF file path.")],
    values: Annotated[
        dict[str, bool | str],
        Field(
            description=(
                "Field name -> value mapping. Use a bool for checkbox/radio fields "
                "and a string for text/choice fields."
            )
        ),
    ],
    password: Annotated[
        str | None, Field(description="Password for an encrypted PDF, if any.")
    ] = None,
) -> ToolOutcome:
    """Fill the named AcroForm fields and regenerate their appearance streams."""
    source = input_path(input_file)
    destination = output_path(output_file, source)
    pdf = open_pdf(source, password)
    try:
        if not pdf.acroform.exists:
            msg = f"PDF has no AcroForm fields to fill: {source}"
            raise PdfToolError(msg)
        for name, value in values.items():
            field = find_field(pdf, name)
            kind = field_kind(field)
            if kind in (FieldKind.CHECKBOX, FieldKind.RADIO):
                on_state = checkbox_on_state(field)
                field.set_value(pikepdf.Name(f"/{on_state}" if value else "/Off"))
            else:
                field.set_value(str(value))
        pdf.acroform.generate_appearances_if_needed()
        written = save_pdf(pdf, destination)
    finally:
        pdf.close()
    return ToolOutcome(output_files=(written,))
