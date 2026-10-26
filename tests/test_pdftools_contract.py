from collections.abc import Callable
from pathlib import Path
from typing import Annotated

import anyio
import pikepdf
import pytest
from mcp.server.fastmcp import FastMCP
from pydantic import Field

from paddlepdf.cli_pdftools import tool_listings
from paddlepdf.mcp_pdftools import McpPdfTool
from paddlepdf.pdftools import (
    ALL_TOOLS,
    PdfToolError,
    ToolOutcome,
    ToolSpec,
    ToolStatus,
    duplicate_tool_names,
    run_tool,
)
from paddlepdf.pdftools.common import open_pdf, output_path, parse_page_ranges

type MakePdf = Callable[..., Path]


def _page_count(
    input_file: Annotated[str, Field(description="PDF to inspect.")],
    password: Annotated[str | None, Field(description="Open password.")] = None,
) -> ToolOutcome:
    with open_pdf(Path(input_file), password) as pdf:
        return ToolOutcome(data={"pages": len(pdf.pages)})


PAGE_COUNT = ToolSpec("probe_page_count", "Count pages.", _page_count)


def test_parse_page_ranges_supports_ranges_last_and_reverse() -> None:
    assert parse_page_ranges("1,3-4,last", 5) == [0, 2, 3, 4]
    assert parse_page_ranges("3-1", 5) == [2, 1, 0]
    assert parse_page_ranges("all", 2) == [0, 1]


@pytest.mark.parametrize("spec", ["0", "6", "1-x", "2--3"])
def test_parse_page_ranges_rejects_bad_specs(spec: str) -> None:
    with pytest.raises(PdfToolError):
        parse_page_ranges(spec, 5)


def test_output_path_refuses_to_overwrite_input(make_pdf: MakePdf) -> None:
    source = make_pdf()
    with pytest.raises(PdfToolError):
        output_path(str(source), source)


def test_run_tool_reports_success_and_expected_failures(make_pdf: MakePdf) -> None:
    source = make_pdf(pages=4)

    ok = run_tool(PAGE_COUNT, {"input_file": str(source)})
    missing = run_tool(PAGE_COUNT, {"input_file": str(source.with_name("no.pdf"))})
    invalid = run_tool(PAGE_COUNT, {"input_file": 5, "bogus": True})

    assert ok.status == ToolStatus.SUCCESS
    assert ok.data == {"pages": 4}
    assert missing.status == ToolStatus.FAILED
    assert missing.errors
    assert invalid.status == ToolStatus.FAILED
    assert invalid.errors[0].startswith("Invalid parameters")


def test_wrong_password_is_a_failed_result(make_pdf: MakePdf, tmp_path: Path) -> None:
    locked = tmp_path / "locked.pdf"
    with pikepdf.open(make_pdf()) as pdf:
        pdf.save(locked, encryption=pikepdf.Encryption(user="right", owner="o"))

    result = run_tool(PAGE_COUNT, {"input_file": str(locked), "password": "wrong"})

    assert result.status == ToolStatus.FAILED
    assert "password" in result.errors[0].lower()


def test_mcp_adapter_exposes_handler_schema_and_runs(make_pdf: MakePdf) -> None:
    server = FastMCP("probe")
    server.add_tool(
        McpPdfTool(PAGE_COUNT), name=PAGE_COUNT.name, structured_output=True
    )
    source = make_pdf(pages=2)

    async def scenario() -> tuple[dict[str, object], object]:
        tool = (await server.list_tools())[0]
        result = await server.call_tool(PAGE_COUNT.name, {"input_file": str(source)})
        return tool.inputSchema, result

    schema, result = anyio.run(scenario)

    assert schema["required"] == ["input_file"]
    assert "password" in str(schema["properties"])
    assert '"pages":2' in str(result).replace(" ", "")


def test_catalog_names_are_unique_and_listed() -> None:
    assert duplicate_tool_names() == ()
    assert [listing.name for listing in tool_listings()] == [
        spec.name for spec in ALL_TOOLS
    ]
