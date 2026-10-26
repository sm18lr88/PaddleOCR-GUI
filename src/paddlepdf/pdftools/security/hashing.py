"""File integrity digests for a PDF."""

import hashlib
from enum import StrEnum
from typing import Annotated

from pydantic import Field, JsonValue

from paddlepdf.pdftools.common import input_path
from paddlepdf.pdftools.contract import PdfToolError, ToolOutcome
from paddlepdf.pdftools.security._params import InputFile


class HashAlgorithm(StrEnum):
    SHA256 = "sha256"
    SHA512 = "sha512"
    SHA1 = "sha1"
    MD5 = "md5"


def pdf_hash(
    input_file: InputFile,
    algorithms: Annotated[
        tuple[HashAlgorithm, ...],
        Field(description="Digest algorithms; the first one is reported as 'hash'."),
    ] = (HashAlgorithm.SHA256,),
) -> ToolOutcome:
    if not algorithms:
        msg = "Choose at least one hash algorithm"
        raise PdfToolError(msg)
    source = input_path(input_file)
    digests: dict[str, JsonValue] = {}
    with source.open("rb") as stream:
        for algorithm in dict.fromkeys(algorithms):
            stream.seek(0)
            digests[algorithm.value] = hashlib.file_digest(
                stream, algorithm.value
            ).hexdigest()
    first = algorithms[0].value
    data: dict[str, JsonValue] = {
        "hash": digests[first],
        "algorithm": first,
        "digests": digests,
        "size_bytes": source.stat().st_size,
    }
    return ToolOutcome(data=data)
