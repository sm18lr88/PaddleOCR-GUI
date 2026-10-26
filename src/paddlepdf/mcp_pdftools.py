"""Expose every pdftools ToolSpec as its own FastMCP tool with the handler's schema."""

import inspect
from functools import partial

from anyio.to_thread import run_sync
from mcp.server.fastmcp import FastMCP

from paddlepdf.pdftools import ALL_TOOLS, ToolResult, ToolSpec, run_tool


class McpPdfTool:
    """Async callable whose signature FastMCP reads; work runs off the event loop."""

    def __init__(self, spec: ToolSpec) -> None:
        self.spec = spec
        self.__name__ = spec.name
        self.__doc__ = spec.description
        self.__signature__ = inspect.signature(spec.handler, eval_str=True).replace(
            return_annotation=ToolResult
        )

    async def __call__(self, **params: object) -> ToolResult:
        return await run_sync(partial(run_tool, self.spec, params))


def register_pdf_tools(server: FastMCP) -> None:
    for spec in ALL_TOOLS:
        server.add_tool(
            McpPdfTool(spec),
            name=spec.name,
            description=spec.description,
            structured_output=True,
        )
