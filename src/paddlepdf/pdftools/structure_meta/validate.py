"""Structural validation."""

from typing import Annotated

from pydantic import Field, JsonValue

from paddlepdf.pdftools.common import input_path, open_pdf
from paddlepdf.pdftools.contract import ToolOutcome


def pdf_validate(
    input_file: Annotated[str, Field(description="Input PDF path.")],
    password: Annotated[str | None, Field(description="Password if encrypted.")] = None,
) -> ToolOutcome:
    path = input_path(input_file)
    with open_pdf(path, password) as pdf:
        problems = [str(problem) for problem in pdf.check_pdf_syntax()]
        page_count = len(pdf.pages)
        if page_count == 0:
            problems.append("Document has 0 pages")
        data: dict[str, JsonValue] = {
            "is_valid": not problems,
            "problems": list[JsonValue](problems),
            "page_count": page_count,
            "version": pdf.pdf_version,
            "encrypted": pdf.is_encrypted,
            "linearized": pdf.is_linearized,
            "object_count": len(pdf.objects),
        }
    return ToolOutcome(data=data, warnings=tuple(problems))
