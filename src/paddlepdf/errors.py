from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from typing_extensions import override


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
        return f"PaddleOCR-VL server unavailable at {self.url}: {self.reason}"


@dataclass(frozen=True, slots=True)
class PaddleDiagnosticOutputError(Exception):
    lines: tuple[str, ...]

    @override
    def __str__(self) -> str:
        return "PaddleOCR emitted warning/error output: " + " | ".join(self.lines)
