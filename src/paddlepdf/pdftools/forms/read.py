"""pdf_read_form: extract AcroForm field names, types, values, and options."""

from typing import Annotated

from pydantic import Field, JsonValue

from paddlepdf.pdftools.common import input_path, open_pdf
from paddlepdf.pdftools.contract import ToolOutcome
from paddlepdf.pdftools.forms._fields import field_kind, field_page_number, field_value


def pdf_read_form(
    input_file: Annotated[str, Field(description="The input PDF file path.")],
    password: Annotated[
        str | None, Field(description="Password for an encrypted PDF, if any.")
    ] = None,
) -> ToolOutcome:
    """Read every AcroForm field's name, type, current value, options, and page."""
    path = input_path(input_file)
    pdf = open_pdf(path, password)
    try:
        if not pdf.acroform.exists:
            return ToolOutcome(data={"fields": []})
        fields: list[JsonValue] = []
        for field in pdf.acroform.fields:
            kind = field_kind(field)
            options: JsonValue = list(field.choices) if field.is_choice else None
            value: JsonValue = field_value(field, kind)
            page: JsonValue = field_page_number(pdf, field)
            fields.append(
                {
                    "name": field.fully_qualified_name,
                    "type": kind.value,
                    "value": value,
                    "options": options,
                    "page": page,
                }
            )
        return ToolOutcome(data={"fields": fields})
    finally:
        pdf.close()
