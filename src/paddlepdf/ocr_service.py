from __future__ import annotations

import time
from pathlib import Path
from typing import TYPE_CHECKING

from paddlepdf.errors import (
    ConversionPathError,
    PaddleDiagnosticOutputError,
    PaddleRuntimeUnavailableError,
    PaddleVlServerUnavailableError,
)
from paddlepdf.models import (
    AgentRunReport,
    ArtifactFormat,
    ConversionOptions,
    ConversionRequest,
    DocumentReport,
    DocumentStatus,
    PlannedDocument,
    ProgressCallback,
    ProgressEvent,
    RunStatus,
)
from paddlepdf.output_files import (
    collect_output_files,
    existing_files,
    save_vl_result,
)
from paddlepdf.paddle_runtime import close_vl_pipeline, create_vl_pipeline
from paddlepdf.planning import (
    SUPPORTED_INPUT_SUFFIXES,
    artifact_formats,
    plan_documents,
)
from paddlepdf.third_party_output import capture_third_party_output, diagnostic_lines

if TYPE_CHECKING:
    from paddleocr import PaddleOCRVL


class PaddleDocumentConverter:
    def convert(
        self,
        request: ConversionRequest,
        progress: ProgressCallback | None = None,
    ) -> AgentRunReport:
        started_at = time.perf_counter()
        reports: list[DocumentReport] = []
        planned = plan_documents(request.input_files, request.output_dir)
        for index, document in enumerate(planned, start=1):
            _emit_progress(
                progress, index, len(planned), document.input_file, "Starting"
            )
            reports.append(
                self._convert_document(
                    document, request.options, progress, index, len(planned)
                )
            )
        return _run_report(request, tuple(reports), time.perf_counter() - started_at)

    def _convert_document(
        self,
        document: PlannedDocument,
        options: ConversionOptions,
        progress: ProgressCallback | None,
        index: int,
        total: int,
    ) -> DocumentReport:
        started_at = time.perf_counter()
        try:
            _validate_input_file(document.input_file)
            if options.dry_run:
                _emit_progress(
                    progress, index, total, document.input_file, "Dry run complete"
                )
                return _dry_run_report(
                    document, options, time.perf_counter() - started_at
                )
            document.output_dir.mkdir(parents=True, exist_ok=True)
            _emit_progress(
                progress, index, total, document.input_file, "Loading OCR engine"
            )
            before = existing_files(document.output_dir)
            _emit_progress(
                progress, index, total, document.input_file, "Parsing document"
            )
            self._convert_with_vl(document, options)
            output_files = collect_output_files(document, options, before)
            _emit_progress(progress, index, total, document.input_file, "Finished")
            return DocumentReport(
                status=DocumentStatus.SUCCESS,
                input_file=document.input_file,
                output_dir=document.output_dir,
                output_files=output_files,
                elapsed_seconds=time.perf_counter() - started_at,
            )
        except (
            ConversionPathError,
            PaddleDiagnosticOutputError,
            PaddleRuntimeUnavailableError,
            PaddleVlServerUnavailableError,
            OSError,
            RuntimeError,
        ) as exc:
            _emit_progress(progress, index, total, document.input_file, "Failed")
            return DocumentReport(
                status=DocumentStatus.FAILED,
                input_file=document.input_file,
                output_dir=document.output_dir,
                errors=(str(exc),),
                elapsed_seconds=time.perf_counter() - started_at,
            )

    def _convert_with_vl(
        self, document: PlannedDocument, options: ConversionOptions
    ) -> None:
        pipeline: PaddleOCRVL | None = None
        with capture_third_party_output() as captured:
            try:
                pipeline = create_vl_pipeline(options)
                formats = artifact_formats(options.output_format)
                for result in pipeline.predict(str(document.input_file)):
                    save_vl_result(result, document.output_dir, formats)
            finally:
                if pipeline is not None:
                    close_vl_pipeline(pipeline)
        if lines := diagnostic_lines(captured):
            raise PaddleDiagnosticOutputError(lines=lines)


def _validate_input_file(input_file: Path) -> None:
    if not input_file.exists():
        raise ConversionPathError(path=input_file, reason="file does not exist")
    if not input_file.is_file():
        raise ConversionPathError(path=input_file, reason="not a file")
    if input_file.suffix.lower() not in SUPPORTED_INPUT_SUFFIXES:
        extensions = ", ".join(sorted(SUPPORTED_INPUT_SUFFIXES))
        raise ConversionPathError(
            path=input_file, reason=f"expected one of: {extensions}"
        )


def _dry_run_report(
    document: PlannedDocument,
    options: ConversionOptions,
    elapsed_seconds: float,
) -> DocumentReport:
    planned_outputs = tuple(
        document.output_dir / f"{document.safe_stem}.{_extension_for_format(format_)}"
        for format_ in artifact_formats(options.output_format)
    )
    return DocumentReport(
        status=DocumentStatus.SUCCESS,
        input_file=document.input_file,
        output_dir=document.output_dir,
        output_files=planned_outputs,
        elapsed_seconds=elapsed_seconds,
    )


def _extension_for_format(format_: ArtifactFormat) -> str:
    match format_:
        case ArtifactFormat.MARKDOWN:
            return "md"
        case ArtifactFormat.JSON:
            return "json"
        case ArtifactFormat.TEXT:
            return "txt"


def _run_report(
    request: ConversionRequest,
    reports: tuple[DocumentReport, ...],
    elapsed_seconds: float,
) -> AgentRunReport:
    output_files = tuple(path for report in reports for path in report.output_files)
    warnings = tuple(warning for report in reports for warning in report.warnings)
    errors = tuple(error for report in reports for error in report.errors)
    return AgentRunReport(
        status=_run_status(reports),
        input_files=request.input_files,
        output_files=output_files,
        warnings=warnings,
        errors=errors,
        elapsed_seconds=elapsed_seconds,
        documents=reports,
    )


def _run_status(reports: tuple[DocumentReport, ...]) -> RunStatus:
    successes = sum(report.status == DocumentStatus.SUCCESS for report in reports)
    failures = len(reports) - successes
    if failures == 0:
        return RunStatus.SUCCESS
    if successes == 0:
        return RunStatus.FAILED
    return RunStatus.PARTIAL


def _emit_progress(
    progress: ProgressCallback | None,
    index: int,
    total: int,
    current_file: Path,
    message: str,
) -> None:
    if progress is not None:
        progress(
            ProgressEvent(
                index=index,
                total=total,
                current_file=current_file,
                message=message,
            ),
        )
