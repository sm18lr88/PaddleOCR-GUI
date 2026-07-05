from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import override
from urllib.parse import urlsplit, urlunsplit


@dataclass(frozen=True, slots=True)
class ConversionPathError(Exception):
    path: Path
    reason: str

    @override
    def __str__(self) -> str:
        return f"{self.path}: {self.reason}"


@dataclass(frozen=True, slots=True)
class PaddleRuntimeUnavailableError(Exception):
    package_name: str

    @override
    def __str__(self) -> str:
        return (
            f"{self.package_name} is not installed. Run the setup commands in "
            "README.md, including PaddlePaddle and paddleocr[doc-parser]."
        )


@dataclass(frozen=True, slots=True)
class PaddleVlServerUnavailableError(Exception):
    url: str
    reason: str

    @override
    def __str__(self) -> str:
        safe_url = _redact_url_userinfo(self.url)
        return f"PaddleOCR-VL server unavailable at {safe_url}: {self.reason}"


@dataclass(frozen=True, slots=True)
class PaddleDiagnosticOutputError(Exception):
    lines: tuple[str, ...]

    @override
    def __str__(self) -> str:
        return "PaddleOCR emitted warning/error output: " + " | ".join(self.lines)


def _redact_url_userinfo(url: str) -> str:
    parsed = urlsplit(url)
    if "@" not in parsed.netloc:
        return url
    safe_netloc = parsed.netloc.rsplit("@", maxsplit=1)[1]
    return urlunsplit(
        (parsed.scheme, safe_netloc, parsed.path, parsed.query, parsed.fragment)
    )
