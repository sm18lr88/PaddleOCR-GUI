from __future__ import annotations

from pathlib import Path
from typing import Annotated, Final

import typer
from rich.console import Console
from rich.progress import BarColumn, Progress, TextColumn, TimeElapsedColumn

from paddlepdf.models import (
    AgentRunReport,
    ConversionOptions,
    ConversionRequest,
    DeviceChoice,
    OutputFormat,
    ProgressEvent,
    QualityProfile,
    RunExitCode,
    RunStatus,
    VlBackend,
)
from paddlepdf.ocr_service import PaddleDocumentConverter

app = typer.Typer(no_args_is_help=True, add_completion=False)
console = Console(stderr=True)
stdout = Console()
DEFAULT_OUTPUT_DIR: Final = Path("output")


@app.callback()
def root() -> None:
    return None


@app.command()
def convert(
    input_files: Annotated[
        list[Path],
        typer.Argument(help="One or more PDF files to convert."),
    ],
    out: Annotated[
        Path,
        typer.Option("--out", "-o", help="Output folder."),
    ] = DEFAULT_OUTPUT_DIR,
    output_format: Annotated[
        OutputFormat,
        typer.Option(
            "--format", "-f", case_sensitive=False, help="markdown, json, text, or all."
        ),
    ] = OutputFormat.MARKDOWN,
    profile: Annotated[
        QualityProfile,
        typer.Option(
            "--profile", case_sensitive=False, help="fast, balanced, or quality."
        ),
    ] = QualityProfile.BALANCED,
    device: Annotated[
        DeviceChoice,
        typer.Option("--device", case_sensitive=False, help="auto, cpu, or gpu."),
    ] = DeviceChoice.GPU,
    vl_backend: Annotated[
        VlBackend,
        typer.Option(
            "--vl-backend",
            case_sensitive=False,
            help="Optimized PaddleOCR-VL server backend: vllm, sglang, or fastdeploy.",
        ),
    ] = VlBackend.VLLM,
    vl_server_url: Annotated[
        str | None,
        typer.Option(
            "--vl-server-url",
            help=(
                "PaddleOCR-VL GenAI server /v1 endpoint. "
                "Also reads PADDLEOCR_VL_SERVER_URL."
            ),
        ),
    ] = None,
    orientation_correction: Annotated[
        bool | None,
        typer.Option(
            "--orientation/--no-orientation",
            help="Enable document orientation correction.",
        ),
    ] = None,
    document_unwarping: Annotated[
        bool | None,
        typer.Option("--unwarp/--no-unwarp", help="Enable document unwarping."),
    ] = None,
    preserve_layout: Annotated[
        bool | None,
        typer.Option(
            "--preserve-layout/--plain-flow",
            help="Keep layout, tables, and formulas where supported.",
        ),
    ] = None,
    agent: Annotated[
        bool,
        typer.Option("--agent", help="Emit deterministic JSON for coding agents."),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run", help="Validate paths and show planned outputs without OCR."
        ),
    ] = False,
) -> None:
    request = ConversionRequest(
        input_files=tuple(path.resolve() for path in input_files),
        output_dir=out.resolve(),
        options=_conversion_options(
            output_format=output_format,
            profile=profile,
            device=device,
            vl_backend=vl_backend,
            vl_server_url=vl_server_url,
            orientation_correction=orientation_correction,
            document_unwarping=document_unwarping,
            preserve_layout=preserve_layout,
            dry_run=dry_run,
        ),
    )
    report = _convert_request(request, agent)
    _write_report(report, agent)
    raise typer.Exit(code=_exit_code(report))


def _conversion_options(
    *,
    output_format: OutputFormat,
    profile: QualityProfile,
    device: DeviceChoice,
    vl_backend: VlBackend,
    vl_server_url: str | None,
    orientation_correction: bool | None,
    document_unwarping: bool | None,
    preserve_layout: bool | None,
    dry_run: bool,
) -> ConversionOptions:
    profile_options = _profile_defaults(profile)
    return ConversionOptions(
        output_format=output_format,
        profile=profile,
        device=device,
        vl_backend=vl_backend,
        vl_server_url=vl_server_url,
        orientation_correction=(
            profile_options.orientation_correction
            if orientation_correction is None
            else orientation_correction
        ),
        document_unwarping=(
            profile_options.document_unwarping
            if document_unwarping is None
            else document_unwarping
        ),
        preserve_layout=(
            profile_options.preserve_layout
            if preserve_layout is None
            else preserve_layout
        ),
        dry_run=dry_run,
    )


def _profile_defaults(profile: QualityProfile) -> ConversionOptions:
    match profile:
        case QualityProfile.FAST:
            return ConversionOptions(
                profile=profile,
                orientation_correction=False,
                document_unwarping=False,
                preserve_layout=True,
            )
        case QualityProfile.BALANCED:
            return ConversionOptions(
                profile=profile,
                orientation_correction=False,
                document_unwarping=False,
                preserve_layout=True,
            )
        case QualityProfile.QUALITY:
            return ConversionOptions(
                profile=profile,
                orientation_correction=True,
                document_unwarping=True,
                preserve_layout=True,
            )


def _convert_request(request: ConversionRequest, agent: bool) -> AgentRunReport:
    converter = PaddleDocumentConverter()
    if agent:
        return converter.convert(request)
    with Progress(
        TextColumn("{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task_id = progress.add_task("Waiting", total=len(request.input_files))

        def update(event: ProgressEvent) -> None:
            progress.update(
                task_id,
                completed=event.index - 1,
                description=f"{event.current_file.name}: {event.message}",
            )

        report = converter.convert(request, progress=update)
        progress.update(
            task_id, completed=len(request.input_files), description="Complete"
        )
        return report


def _write_report(report: AgentRunReport, agent: bool) -> None:
    if agent:
        stdout.print(report.model_dump_json(indent=2))
        return
    console.print(f"Status: [bold]{report.status.value}[/bold]")
    console.print(f"Output files: {len(report.output_files)}")
    for document in report.documents:
        input_name = document.input_file.name
        output_dir = document.output_dir
        document_line = f"- {input_name}: {document.status.value} -> {output_dir}"
        console.print(document_line)
        for error in document.errors:
            console.print(f"  [red]{error}[/red]")


def _exit_code(report: AgentRunReport) -> RunExitCode:
    match report.status:
        case RunStatus.SUCCESS:
            return 0
        case RunStatus.PARTIAL | RunStatus.FAILED:
            return 1


def main() -> None:
    app()
