"""`paddlepdf tool list|run`: the CLI face of pdftools, same report as the MCP tools.

Exit code 0 means success; 1 means the tool failed, was unknown, or params were bad.
"""

import json
import sys
from pathlib import Path
from typing import Annotated

import typer
from pydantic import BaseModel, ConfigDict, JsonValue, TypeAdapter

from paddlepdf.pdftools import ALL_TOOLS, ToolResult, ToolStatus, find_tool, run_tool

tool_app = typer.Typer(
    no_args_is_help=True,
    add_completion=False,
    help="Edit, organize, secure, sign, and convert PDFs without OCR.",
)


class ToolListing(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    description: str
    input_schema: dict[str, JsonValue]


def tool_listings() -> tuple[ToolListing, ...]:
    return tuple(
        ToolListing(
            name=spec.name,
            description=spec.description,
            input_schema=TypeAdapter(spec.handler).json_schema(),
        )
        for spec in ALL_TOOLS
    )


@tool_app.command("list")
def list_tools(
    agent: Annotated[
        bool, typer.Option("--agent", help="Emit JSON with each input schema.")
    ] = False,
) -> None:
    listings = tool_listings()
    if agent:
        payload = [listing.model_dump(mode="json") for listing in listings]
        sys.stdout.write(json.dumps(payload, indent=2) + "\n")
        return
    for listing in listings:
        sys.stdout.write(f"{listing.name}: {listing.description}\n")


@tool_app.command("run")
def run(
    name: Annotated[str, typer.Argument(help="Tool name from `paddlepdf tool list`.")],
    params: Annotated[
        str, typer.Option("--params", "-p", help="JSON object of tool arguments.")
    ] = "{}",
    params_file: Annotated[
        str | None,
        typer.Option("--params-file", help="Read the JSON arguments from a file."),
    ] = None,
    agent: Annotated[
        bool, typer.Option("--agent", help="Emit deterministic JSON.")
    ] = False,
) -> None:
    result = _run_named_tool(name, params, params_file)
    if agent:
        sys.stdout.write(result.model_dump_json(indent=2) + "\n")
    else:
        sys.stdout.write(f"{result.tool}: {result.status.value}\n")
        for line in (*result.output_files, *result.warnings, *result.errors):
            sys.stdout.write(f"  {line}\n")
    raise typer.Exit(code=0 if result.status == ToolStatus.SUCCESS else 1)


def _run_named_tool(name: str, params: str, params_file: str | None) -> ToolResult:
    spec = find_tool(name)
    if spec is None:
        return _failed(name, f"Unknown tool {name!r}; run `paddlepdf tool list`.")
    try:
        text = Path(params_file).read_text(encoding="utf-8") if params_file else params
        arguments = TypeAdapter(dict[str, JsonValue]).validate_json(text)
    except (OSError, ValueError) as error:
        return _failed(name, f"Invalid --params JSON object: {error}")
    return run_tool(spec, arguments)


def _failed(name: str, message: str) -> ToolResult:
    return ToolResult(status=ToolStatus.FAILED, tool=name, errors=(message,))
