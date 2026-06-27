from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field

MODEL_PIPELINE_VERSION: Final = "v1.6"


class OutputFormat(StrEnum):
    MARKDOWN = "markdown"
    JSON = "json"
    TEXT = "text"
    ALL = "all"


class ArtifactFormat(StrEnum):
    MARKDOWN = "markdown"
    JSON = "json"
    TEXT = "text"


class DeviceChoice(StrEnum):
    AUTO = "auto"
    CPU = "cpu"
    GPU = "gpu"


class VlBackend(StrEnum):
    VLLM = "vllm"
    SGLANG = "sglang"
    FASTDEPLOY = "fastdeploy"


class QualityProfile(StrEnum):
    FAST = "fast"
    BALANCED = "balanced"
    QUALITY = "quality"


class DocumentStatus(StrEnum):
    SUCCESS = "success"
    FAILED = "failed"


class RunStatus(StrEnum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"


class ConversionOptions(BaseModel):
    model_config = ConfigDict(frozen=True)

    output_format: OutputFormat = OutputFormat.MARKDOWN
    profile: QualityProfile = QualityProfile.BALANCED
    device: DeviceChoice = DeviceChoice.GPU
    vl_backend: VlBackend = VlBackend.VLLM
    vl_server_url: str | None = None
    orientation_correction: bool = False
    document_unwarping: bool = False
    preserve_layout: bool = True
    dry_run: bool = False


class ConversionRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    input_files: tuple[Path, ...] = Field(min_length=1)
    output_dir: Path
    options: ConversionOptions


class DocumentReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: DocumentStatus
    input_file: Path
    output_dir: Path
    output_files: tuple[Path, ...] = ()
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()
    elapsed_seconds: float = 0.0


class AgentRunReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: RunStatus
    input_files: tuple[Path, ...]
    output_files: tuple[Path, ...]
    warnings: tuple[str, ...]
    errors: tuple[str, ...]
    elapsed_seconds: float
    documents: tuple[DocumentReport, ...]


@dataclass(frozen=True, slots=True)
class PlannedDocument:
    input_file: Path
    output_dir: Path
    safe_stem: str


@dataclass(frozen=True, slots=True)
class ProgressEvent:
    index: int
    total: int
    current_file: Path
    message: str


ProgressCallback = Callable[[ProgressEvent], None]

RunExitCode = Literal[0, 1, 2]
