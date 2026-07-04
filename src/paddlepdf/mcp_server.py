from pathlib import Path
from typing import Annotated

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, ConfigDict, Field

from paddlepdf.models import (
    AgentRunReport,
    ConversionOptions,
    ConversionRequest,
    DeviceChoice,
    OutputFormat,
    QualityProfile,
    VlBackend,
)
from paddlepdf.ocr_service import PaddleDocumentConverter


class McpConversionRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    input_files: tuple[str, ...] = Field(min_length=1)
    output_dir: str
    output_format: OutputFormat = OutputFormat.MARKDOWN
    profile: QualityProfile = QualityProfile.BALANCED
    device: DeviceChoice = DeviceChoice.GPU
    vl_backend: VlBackend = VlBackend.VLLM
    vl_server_url: str | None = None
    orientation_correction: bool = False
    document_unwarping: bool = False
    preserve_layout: bool = True
    dry_run: bool = False


class McpDocumentReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: str
    input_file: str
    output_dir: str
    output_files: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()
    elapsed_seconds: float = 0.0


class McpAgentRunReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: str
    input_files: tuple[str, ...]
    output_files: tuple[str, ...]
    warnings: tuple[str, ...]
    errors: tuple[str, ...]
    elapsed_seconds: float
    documents: tuple[McpDocumentReport, ...]


mcp = FastMCP(
    "paddlepdf",
    log_level="ERROR",
    instructions=(
        "Convert PDFs and common document images with PaddleOCR-VL. "
        "Use dry_run=true to validate paths without contacting the VL server."
    ),
)


@mcp.tool(
    name="convert_documents",
    description=(
        "Convert PDF/image files with PaddleOCR-VL and return the same "
        "structured report as CLI --agent output."
    ),
)
def convert_documents(
    input_files: Annotated[
        tuple[str, ...],
        Field(
            min_length=1,
            description=(
                "PDF/image files to convert. Supported: pdf, png, jpg, jpeg, "
                "tif, tiff, bmp, webp."
            ),
        ),
    ],
    output_dir: Annotated[str, Field(description="Folder that receives outputs.")],
    output_format: Annotated[
        OutputFormat,
        Field(description="Artifact format to write."),
    ] = OutputFormat.MARKDOWN,
    profile: Annotated[
        QualityProfile,
        Field(description="OCR quality profile."),
    ] = QualityProfile.BALANCED,
    device: Annotated[
        DeviceChoice,
        Field(description="Paddle device selector."),
    ] = DeviceChoice.GPU,
    vl_backend: Annotated[
        VlBackend,
        Field(description="Optimized PaddleOCR-VL GenAI server backend."),
    ] = VlBackend.VLLM,
    vl_server_url: Annotated[
        str | None,
        Field(description="PaddleOCR-VL GenAI server /v1 endpoint."),
    ] = None,
    orientation_correction: Annotated[
        bool,
        Field(description="Enable document orientation correction."),
    ] = False,
    document_unwarping: Annotated[
        bool,
        Field(description="Enable document unwarping."),
    ] = False,
    preserve_layout: Annotated[
        bool,
        Field(description="Preserve layout, tables, and formulas where supported."),
    ] = True,
    dry_run: Annotated[
        bool,
        Field(
            description=(
                "Validate inputs and planned outputs without contacting "
                "PaddleOCR-VL."
            ),
        ),
    ] = False,
) -> McpAgentRunReport:
    report = convert_mcp_request(
        McpConversionRequest(
            input_files=input_files,
            output_dir=output_dir,
            output_format=output_format,
            profile=profile,
            device=device,
            vl_backend=vl_backend,
            vl_server_url=vl_server_url,
            orientation_correction=orientation_correction,
            document_unwarping=document_unwarping,
            preserve_layout=preserve_layout,
            dry_run=dry_run,
        )
    )
    return mcp_report(report)


def convert_mcp_request(request: McpConversionRequest) -> AgentRunReport:
    conversion_request = ConversionRequest(
        input_files=tuple(Path(path).resolve() for path in request.input_files),
        output_dir=Path(request.output_dir).resolve(),
        options=ConversionOptions(
            output_format=request.output_format,
            profile=request.profile,
            device=request.device,
            vl_backend=request.vl_backend,
            vl_server_url=request.vl_server_url,
            orientation_correction=request.orientation_correction,
            document_unwarping=request.document_unwarping,
            preserve_layout=request.preserve_layout,
            dry_run=request.dry_run,
        ),
    )
    return PaddleDocumentConverter().convert(conversion_request)


def mcp_report(report: AgentRunReport) -> McpAgentRunReport:
    return McpAgentRunReport(
        status=report.status.value,
        input_files=tuple(str(path) for path in report.input_files),
        output_files=tuple(str(path) for path in report.output_files),
        warnings=report.warnings,
        errors=report.errors,
        elapsed_seconds=report.elapsed_seconds,
        documents=tuple(
            McpDocumentReport(
                status=document.status.value,
                input_file=str(document.input_file),
                output_dir=str(document.output_dir),
                output_files=tuple(str(path) for path in document.output_files),
                warnings=document.warnings,
                errors=document.errors,
                elapsed_seconds=document.elapsed_seconds,
            )
            for document in report.documents
        ),
    )


def main() -> None:
    mcp.run()
