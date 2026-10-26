from pathlib import Path
from typing import Annotated

import aiohttp
from pydantic import Field
from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
from pyhanko.pdf_utils.misc import PdfError as HankoPdfError
from pyhanko.sign.general import SigningError
from pyhanko.sign.signers import PdfTimeStamper
from pyhanko.sign.timestamps import HTTPTimeStamper, TimeStamper

from paddlepdf.pdftools.common import input_path, output_path
from paddlepdf.pdftools.contract import PdfToolError, ToolOutcome


def apply_timestamp(
    source: Path, target: Path, timestamper: TimeStamper, password: str | None
) -> None:
    """Append an RFC 3161 document timestamp as an incremental update."""
    try:
        with source.open("rb") as handle, target.open("wb") as out:
            writer = IncrementalPdfFileWriter(handle)
            if writer.prev.encrypted:
                writer.encrypt(password or "")
            PdfTimeStamper(timestamper).timestamp_pdf(writer, "sha256", output=out)
    except (
        SigningError,
        HankoPdfError,
        aiohttp.ClientError,
        TimeoutError,
        OSError,
    ) as error:
        target.unlink(missing_ok=True)
        msg = f"Timestamping {source} failed: {error}"
        raise PdfToolError(msg) from error


def pdf_timestamp(
    input_file: Annotated[str, Field(description="Source PDF path.")],
    output_file: Annotated[str, Field(description="Destination PDF path.")],
    tsa_url: Annotated[
        str,
        Field(description="RFC 3161 TSA URL (network access required)."),
    ] = "http://timestamp.digicert.com",
    timeout_seconds: Annotated[
        float, Field(gt=0, description="TSA request timeout in seconds.")
    ] = 15.0,
    password: Annotated[
        str | None, Field(description="Password of an encrypted input.")
    ] = None,
) -> ToolOutcome:
    source = input_path(input_file)
    target = output_path(output_file, source)
    timestamper = HTTPTimeStamper(tsa_url, timeout=round(timeout_seconds))
    apply_timestamp(source, target, timestamper, password)
    return ToolOutcome(output_files=(str(target),), data={"tsa_url": tsa_url})
