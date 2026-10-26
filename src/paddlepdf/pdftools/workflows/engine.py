"""Sequential step runner that chains each tool's output file into the next input."""

import inspect
import tempfile
import time
from collections.abc import Mapping, Sequence
from pathlib import Path

from pydantic import AliasChoices, BaseModel, Field, JsonValue

from paddlepdf.pdftools.common import output_path
from paddlepdf.pdftools.contract import PdfToolError, ToolSpec, ToolStatus
from paddlepdf.pdftools.registry import find_base_tool
from paddlepdf.pdftools.runner import run_tool

RECURSIVE_TOOLS = frozenset({"list_workflows", "document_workflow", "workflow"})
READING_TOOLS = frozenset(
    {
        "extract_text",
        "ocr",
        "to_markdown",
        "to_html",
        "to_json",
        "rag_chunks",
        "search",
        "workspace_search",
    }
)
PARAM_ALIASES = {"start": "start_number"}
MANAGED_PARAMS = ("input_file", "output_file")


class WorkflowStep(BaseModel):
    tool: str = Field(
        validation_alias=AliasChoices("tool", "operationId", "operation_id"),
        description="Name of a pdf_* editing tool, e.g. pdf_watermark.",
    )
    params: dict[str, JsonValue] = Field(
        default_factory=dict,
        description="Tool parameters except input_file/output_file, which are chained.",
    )
    label: str | None = None


class Recipe(BaseModel):
    id: str = "custom-recipe"
    name: str = "Custom workflow"
    steps: list[WorkflowStep]


def resolve_tool(name: str) -> ToolSpec:
    stripped = name.strip()
    bare = stripped.removeprefix("pdf_")
    if stripped in RECURSIVE_TOOLS or bare in RECURSIVE_TOOLS:
        msg = f"Workflows cannot call {stripped!r}; recursion is refused."
        raise PdfToolError(msg)
    if bare in READING_TOOLS:
        msg = (
            f"Tool {stripped!r} is not available in workflows; "
            "use convert_documents to read PDF content."
        )
        raise PdfToolError(msg)
    spec = find_base_tool(stripped) or find_base_tool(f"pdf_{stripped}")
    if spec is None:
        msg = f"Unknown workflow tool {stripped!r}."
        raise PdfToolError(msg)
    parameters = inspect.signature(spec.handler).parameters
    if any(key not in parameters for key in MANAGED_PARAMS):
        msg = (
            f"Tool {spec.name!r} cannot be chained: it does not take one "
            "input_file and one output_file."
        )
        raise PdfToolError(msg)
    return spec


def apply_overrides(
    step: WorkflowStep,
    spec: ToolSpec,
    overrides: Mapping[str, Mapping[str, JsonValue]],
) -> dict[str, JsonValue]:
    parameters = inspect.signature(spec.handler).parameters
    merged = dict(step.params)
    for key in (step.tool.strip(), spec.name):
        merged.update(overrides.get(key, {}))
    renamed = {
        (
            PARAM_ALIASES[key]
            if key in PARAM_ALIASES and key not in parameters
            else key
        ): value
        for key, value in merged.items()
    }
    managed = [key for key in MANAGED_PARAMS if key in renamed]
    if managed:
        names = ", ".join(managed)
        msg = f"Step {spec.name!r} must not set {names}; workflows chain them."
        raise PdfToolError(msg)
    return renamed


def run_steps(
    steps: Sequence[WorkflowStep],
    overrides: Mapping[str, Mapping[str, JsonValue]],
    input_file: Path,
    output_file: Path,
    password: str | None,
) -> tuple[list[JsonValue], tuple[str, ...], tuple[str, ...]]:
    if not steps:
        msg = "A workflow needs at least one step."
        raise PdfToolError(msg)
    plans = [
        (spec, apply_overrides(step, spec, overrides), step.label or spec.name)
        for step in steps
        for spec in (resolve_tool(step.tool),)
    ]
    reports: list[JsonValue] = []
    warnings: list[str] = []
    outputs: tuple[str, ...] = (str(output_file),)
    current = input_file
    with tempfile.TemporaryDirectory(
        dir=output_file.parent, prefix=".workflow-"
    ) as work:
        for index, (spec, params, label) in enumerate(plans, start=1):
            is_last = index == len(plans)
            target = (
                output_file if is_last else Path(work) / f"step-{index}-{spec.name}.pdf"
            )
            call: dict[str, object] = {
                **params,
                "input_file": str(current),
                "output_file": str(target),
            }
            takes_password = "password" in inspect.signature(spec.handler).parameters
            if index == 1 and password and takes_password:
                call.setdefault("password", password)
            started = time.perf_counter()
            result = run_tool(spec, call)
            if result.status is not ToolStatus.SUCCESS:
                msg = f"Step {index} ({spec.name}) failed: {'; '.join(result.errors)}"
                raise PdfToolError(msg)
            warnings.extend(
                f"Step {index} ({spec.name}): {text}" for text in result.warnings
            )
            reports.append(
                {
                    "index": index,
                    "tool": spec.name,
                    "label": label,
                    "status": result.status.value,
                    "elapsed_seconds": time.perf_counter() - started,
                }
            )
            current = Path(result.output_files[0]) if result.output_files else target
            if is_last and result.output_files:
                outputs = result.output_files
    return reports, outputs, tuple(warnings)


def checked_output(output_file: str, input_file: Path) -> Path:
    return output_path(output_file, input_file)
