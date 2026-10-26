from typing import IO

from xhtml2pdf.config.resources import ResourceAccessPolicy

class pisaContext:
    err: int
    warn: int
    log: list[tuple[str, int, str, str]]

def CreatePDF(
    src: str | bytes | IO[str] | IO[bytes],
    dest: IO[bytes] | None = ...,
    path: str = ...,
    encoding: str | None = ...,
    resource_policy: ResourceAccessPolicy | None = ...,
) -> pisaContext: ...
