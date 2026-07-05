from __future__ import annotations

import sys
from dataclasses import dataclass
from io import StringIO
from types import TracebackType
from typing import Final, TextIO

DIAGNOSTIC_MARKERS: Final = (
    "warning",
    "error",
    "exception",
    "traceback",
    "deprecated",
    "deprecation",
)
BENIGN_TENSOR_WARNING_PREFIX: Final = (
    "To copy construct from a tensor, it is recommended to use "
)
BENIGN_TENSOR_WARNING_SUFFIX: Final = (
    "sourceTensor.clone().detach(), rather than paddle.to_tensor(sourceTensor)."
)
BENIGN_DIAGNOSTIC_SNIPPETS: Final = (
    BENIGN_TENSOR_WARNING_PREFIX + BENIGN_TENSOR_WARNING_SUFFIX,
)


@dataclass(frozen=True, slots=True)
class CapturedStreams:
    stdout: StringIO
    stderr: StringIO


class ThirdPartyOutputCapture:
    def __init__(self) -> None:
        self.captured = CapturedStreams(stdout=StringIO(), stderr=StringIO())
        self._previous_stdout: TextIO | None = None
        self._previous_stderr: TextIO | None = None

    def __enter__(self) -> CapturedStreams:
        self._previous_stdout = sys.stdout
        self._previous_stderr = sys.stderr
        sys.stdout = self.captured.stdout
        sys.stderr = self.captured.stderr
        return self.captured

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self._previous_stdout is not None:
            sys.stdout = self._previous_stdout
        if self._previous_stderr is not None:
            sys.stderr = self._previous_stderr


def capture_third_party_output() -> ThirdPartyOutputCapture:
    return ThirdPartyOutputCapture()


def diagnostic_lines(captured: CapturedStreams) -> tuple[str, ...]:
    lines = (
        *captured.stdout.getvalue().splitlines(),
        *captured.stderr.getvalue().splitlines(),
    )
    return tuple(
        line
        for line in lines
        if _has_diagnostic_marker(line) and not _is_benign_diagnostic(line)
    )


def _has_diagnostic_marker(line: str) -> bool:
    normalized = line.casefold()
    return any(marker in normalized for marker in DIAGNOSTIC_MARKERS)


def _is_benign_diagnostic(line: str) -> bool:
    return any(snippet in line for snippet in BENIGN_DIAGNOSTIC_SNIPPETS)
