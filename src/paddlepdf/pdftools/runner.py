import time
from collections.abc import Mapping

import pikepdf
from pydantic import ValidationError, validate_call

from paddlepdf.pdftools.contract import PdfToolError, ToolResult, ToolSpec, ToolStatus

EXPECTED_FAILURES = (PdfToolError, ValidationError, OSError, pikepdf.PdfError)


def run_tool(spec: ToolSpec, params: Mapping[str, object]) -> ToolResult:
    started = time.perf_counter()
    try:
        outcome = validate_call(spec.handler)(**params)
    except EXPECTED_FAILURES as error:
        return ToolResult(
            status=ToolStatus.FAILED,
            tool=spec.name,
            errors=(_error_message(error),),
            elapsed_seconds=time.perf_counter() - started,
        )
    return ToolResult(
        status=ToolStatus.SUCCESS,
        tool=spec.name,
        output_files=outcome.output_files,
        data=outcome.data,
        warnings=outcome.warnings,
        elapsed_seconds=time.perf_counter() - started,
    )


def _error_message(error: Exception) -> str:
    if isinstance(error, ValidationError):
        return f"Invalid parameters: {error}"
    return str(error) or type(error).__name__
