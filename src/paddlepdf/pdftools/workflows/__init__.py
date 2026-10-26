"""Declarative multi-step workflows that chain the other PDF editing tools."""

import time
from pathlib import Path
from typing import Annotated

from pydantic import Field, JsonValue

from paddlepdf.pdftools.common import input_path
from paddlepdf.pdftools.contract import PdfToolError, ToolOutcome, ToolSpec
from paddlepdf.pdftools.workflows.engine import (
    Recipe,
    WorkflowStep,
    checked_output,
    run_steps,
)
from paddlepdf.pdftools.workflows.presets import PRESETS, find_preset

PRESET_HELP = (
    "Preset id such as preset-legal-discovery, preset-clean-scan or "
    "preset-redact-protect (the 'preset-' prefix is optional). See list_workflows."
)
STEP_PARAMS_HELP = (
    "Per-tool parameter overrides keyed by tool name, e.g. "
    '{"pdf_redact": {"search_text": "secret"}, "pdf_encrypt": {"user_password": "pw"}}.'
)


def list_workflows() -> ToolOutcome:
    presets: list[JsonValue] = [
        {
            "id": preset.id,
            "name": preset.name,
            "description": preset.description,
            "is_preset": True,
            "required_step_params": dict(preset.required_step_params),
            "steps": [
                {"tool": step.tool, "label": step.label, "params": dict(step.params)}
                for step in preset.steps
            ],
        }
        for preset in PRESETS
    ]
    return ToolOutcome(data=presets)


def document_workflow(
    input_file: Annotated[str, Field(description="Path to the input PDF.")],
    output_file: Annotated[str, Field(description="Path of the final output file.")],
    preset: Annotated[str | None, Field(description=PRESET_HELP)] = None,
    steps: Annotated[
        list[WorkflowStep] | None,
        Field(description="Custom pipeline: ordered [{tool, params}] of pdf_* tools."),
    ] = None,
    recipe: Annotated[
        str | None,
        Field(description="Path to a recipe JSON file, or a raw recipe JSON string."),
    ] = None,
    step_params: Annotated[
        dict[str, dict[str, JsonValue]] | None,
        Field(description=STEP_PARAMS_HELP),
    ] = None,
    password: Annotated[
        str | None,
        Field(description="Password of the input PDF, used by the first step."),
    ] = None,
) -> ToolOutcome:
    sources = (("preset", preset), ("steps", steps), ("recipe", recipe))
    if sum(1 for _, value in sources if value) != 1:
        msg = "Specify exactly one of 'preset', 'steps' or 'recipe'."
        raise PdfToolError(msg)
    source = input_path(input_file)
    target = checked_output(output_file, source)
    workflow_id, workflow_name, plan = _resolve_plan(preset, steps, recipe)
    started = time.perf_counter()
    reports, outputs, warnings = run_steps(
        plan, step_params or {}, source, target, password
    )
    return ToolOutcome(
        output_files=outputs,
        warnings=warnings,
        data={
            "workflow_id": workflow_id,
            "workflow_name": workflow_name,
            "steps_total": len(plan),
            "steps_completed": len(reports),
            "steps": reports,
            "duration_ms": round((time.perf_counter() - started) * 1000),
        },
    )


def _resolve_plan(
    preset: str | None, steps: list[WorkflowStep] | None, recipe: str | None
) -> tuple[str, str, list[WorkflowStep]]:
    if preset:
        found = find_preset(preset)
        if found is None:
            known = ", ".join(item.id for item in PRESETS)
            msg = f"Preset not found: {preset}. Available: {known}."
            raise PdfToolError(msg)
        plan = [
            WorkflowStep(tool=step.tool, params=dict(step.params), label=step.label)
            for step in found.steps
        ]
        return found.id, found.name, plan
    if recipe:
        text = (
            recipe
            if recipe.lstrip().startswith("{")
            else Path(recipe).read_text("utf-8")
        )
        parsed = Recipe.model_validate_json(text)
        return parsed.id, parsed.name, parsed.steps
    return "custom-steps", "Custom workflow", list(steps or [])


TOOLS: tuple[ToolSpec, ...] = (
    ToolSpec(
        name="list_workflows",
        description=(
            "List the preset document workflows (id, name, steps, and which step "
            "parameters must be supplied). Use an id with document_workflow."
        ),
        handler=list_workflows,
    ),
    ToolSpec(
        name="document_workflow",
        description=(
            "Run a multi-step PDF pipeline from a preset id, a custom steps list, or a "
            "recipe, chaining each step's output into the next; stops at the first "
            "failing step. Writes the final PDF to output_file; returns per-step data."
        ),
        handler=document_workflow,
    ),
)
