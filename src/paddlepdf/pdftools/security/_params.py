"""Parameter annotations shared by the security tool signatures."""

from typing import Annotated

from pydantic import Field

InputFile = Annotated[str, Field(description="Path of the PDF to read.")]
OutputFile = Annotated[str, Field(description="Path of the PDF to write.")]
InputPassword = Annotated[
    str | None,
    Field(description="Password needed to open an already encrypted input PDF."),
]
