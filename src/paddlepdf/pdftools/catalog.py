from paddlepdf.pdftools.contract import ToolSpec
from paddlepdf.pdftools.registry import BASE_TOOLS
from paddlepdf.pdftools.workflows import TOOLS as WORKFLOW_TOOLS

ALL_TOOLS: tuple[ToolSpec, ...] = (*BASE_TOOLS, *WORKFLOW_TOOLS)


def find_tool(name: str) -> ToolSpec | None:
    return next((spec for spec in ALL_TOOLS if spec.name == name), None)


def duplicate_tool_names() -> tuple[str, ...]:
    names = [spec.name for spec in ALL_TOOLS]
    return tuple(sorted({name for name in names if names.count(name) > 1}))
