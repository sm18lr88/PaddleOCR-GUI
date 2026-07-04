from collections.abc import Mapping, Sequence
from pathlib import Path

import anyio
from mcp.types import Tool
from pydantic import BaseModel, ConfigDict, Field

from paddlepdf.mcp_server import McpConversionRequest, convert_mcp_request, mcp
from paddlepdf.models import OutputFormat, RunStatus


def test_mcp_convert_documents_dry_run_accepts_pdf_and_image(
    tmp_path: Path,
) -> None:
    input_pdf = tmp_path / "paper.pdf"
    input_image = tmp_path / "scan.png"
    input_pdf.write_bytes(b"%PDF-1.4\n")
    input_image.write_bytes(b"not-a-real-image")

    report = convert_mcp_request(
        McpConversionRequest(
            input_files=(str(input_pdf), str(input_image)),
            output_dir=str(tmp_path / "out"),
            output_format=OutputFormat.ALL,
            dry_run=True,
        )
    )

    assert report.status == RunStatus.SUCCESS
    assert len(report.documents) == 2
    assert len(report.output_files) == 6
    assert report.warnings == ()
    assert report.errors == ()


type JsonValue = JsonScalar | JsonObject | JsonArray
type JsonScalar = str | int | float | bool | None
type JsonObject = Mapping[str, JsonValue]
type JsonArray = Sequence[JsonValue]


class ToolSchemaView(BaseModel):
    model_config = ConfigDict(frozen=True)

    input_schema: JsonObject = Field(alias="inputSchema")
    output_schema: JsonObject | None = Field(default=None, alias="outputSchema")


def test_mcp_tool_schema_uses_flat_arguments() -> None:
    convert_tool = _convert_documents_tool()
    input_schema = _tool_input_schema(convert_tool)

    assert "request" not in _schema_property_names(input_schema)
    assert _schema_required_fields(input_schema) == ("input_files", "output_dir")
    assert "input_files" in _schema_property_names(input_schema)
    assert "output_dir" in _schema_property_names(input_schema)


def test_mcp_tool_schema_has_no_path_format() -> None:
    convert_tool = _convert_documents_tool()
    input_schema = _tool_input_schema(convert_tool)
    output_schema = _tool_output_schema(convert_tool)

    assert not _schema_contains_path_format(input_schema)
    assert output_schema is not None
    assert not _schema_contains_path_format(output_schema)


def _convert_documents_tool() -> Tool:
    return anyio.run(_load_convert_documents_tool)


async def _load_convert_documents_tool() -> Tool:
    tools = await mcp.list_tools()
    return next(tool for tool in tools if tool.name == "convert_documents")


def _tool_input_schema(tool: Tool) -> JsonObject:
    return ToolSchemaView.model_validate(tool.model_dump()).input_schema


def _tool_output_schema(tool: Tool) -> JsonObject | None:
    return ToolSchemaView.model_validate(tool.model_dump()).output_schema


def _schema_property_names(schema: JsonObject) -> frozenset[str]:
    properties = schema.get("properties")
    if not isinstance(properties, Mapping):
        return frozenset()
    return frozenset(str(key) for key in properties)


def _schema_required_fields(schema: JsonObject) -> tuple[str, ...]:
    required = schema.get("required")
    if not isinstance(required, Sequence) or isinstance(required, str):
        return ()
    return tuple(str(value) for value in required)


def _schema_contains_path_format(schema: JsonValue) -> bool:
    if isinstance(schema, Mapping):
        if schema.get("format") == "path":
            return True
        return any(_schema_contains_path_format(value) for value in schema.values())
    if isinstance(schema, Sequence) and not isinstance(schema, str):
        return any(_schema_contains_path_format(value) for value in schema)
    return False
