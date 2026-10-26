import subprocess
import sys
from dataclasses import dataclass
from typing import override

from pydantic import BaseModel, ConfigDict, Field

from paddlepdf.models import (
    AgentRunReport,
    DeviceChoice,
    OutputFormat,
    QualityProfile,
    VlBackend,
)


class McpConversionRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    input_files: tuple[str, ...] = Field(min_length=1)
    output_dir: str
    output_format: OutputFormat = OutputFormat.MARKDOWN
    profile: QualityProfile = QualityProfile.BALANCED
    vl_backend: VlBackend = VlBackend.VLLM
    vl_server_url: str | None = None
    orientation_correction: bool = False
    document_unwarping: bool = False
    preserve_layout: bool = True
    dry_run: bool = False


@dataclass(frozen=True, slots=True)
class McpConversionSubprocessError(Exception):
    return_code: int
    stderr: str

    @override
    def __str__(self) -> str:
        return (
            f"PaddlePDF conversion process exited with code {self.return_code}: "
            f"{self.stderr}"
        )


def convert_mcp_request_in_subprocess(
    request: McpConversionRequest,
) -> AgentRunReport:
    completed = subprocess.run(  # noqa: S603 - fixed interpreter without a shell.
        mcp_conversion_command(request),
        check=False,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=(subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0),
    )
    if completed.returncode not in (0, 1):
        raise McpConversionSubprocessError(
            return_code=completed.returncode,
            stderr=completed.stderr.strip(),
        )
    return AgentRunReport.model_validate_json(completed.stdout)


def mcp_conversion_command(request: McpConversionRequest) -> list[str]:
    command = [
        sys.executable,
        "-m",
        "paddlepdf",
        "convert",
        *request.input_files,
        "--out",
        request.output_dir,
        "--format",
        request.output_format.value,
        "--profile",
        request.profile.value,
        "--device",
        DeviceChoice.GPU.value,
        "--vl-backend",
        request.vl_backend.value,
        "--orientation" if request.orientation_correction else "--no-orientation",
        "--unwarp" if request.document_unwarping else "--no-unwarp",
        "--preserve-layout" if request.preserve_layout else "--plain-flow",
        "--agent",
    ]
    if request.vl_server_url is not None:
        command.extend(("--vl-server-url", request.vl_server_url))
    if request.dry_run:
        command.append("--dry-run")
    return command
