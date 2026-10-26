"""Parameter annotations shared by the structure_ops handlers (they form the schema)."""

from typing import Annotated

import pikepdf
from pydantic import Field

InputFile = Annotated[str, Field(description="Path to the source PDF.")]
OutputFile = Annotated[str, Field(description="Path for the output PDF.")]
OutputDir = Annotated[
    str, Field(description="Directory to write output files into (created if missing).")
]
Pages = Annotated[
    str,
    Field(description="1-based pages like '1,3-5,last', or 'all' for every page."),
]
Password = Annotated[
    str | None, Field(description="Password if the input PDF is encrypted.")
]

DECRYPTED_WARNING = (
    "Input was encrypted; the output is saved without encryption. "
    "Re-encrypt it with a security tool if needed."
)


def encryption_warnings(pdf: pikepdf.Pdf) -> tuple[str, ...]:
    return (DECRYPTED_WARNING,) if pdf.is_encrypted else ()
