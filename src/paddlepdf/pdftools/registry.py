"""Operational tools from every lane except workflows, which compose these."""

from paddlepdf.pdftools.contract import ToolSpec
from paddlepdf.pdftools.create import TOOLS as CREATE_TOOLS
from paddlepdf.pdftools.forms import TOOLS as FORMS_TOOLS
from paddlepdf.pdftools.layout import TOOLS as LAYOUT_TOOLS
from paddlepdf.pdftools.marking import TOOLS as MARKING_TOOLS
from paddlepdf.pdftools.office import TOOLS as OFFICE_TOOLS
from paddlepdf.pdftools.pages_basic import TOOLS as PAGES_BASIC_TOOLS
from paddlepdf.pdftools.pages_geometry import TOOLS as PAGES_GEOMETRY_TOOLS
from paddlepdf.pdftools.security import TOOLS as SECURITY_TOOLS
from paddlepdf.pdftools.signatures import TOOLS as SIGNATURES_TOOLS
from paddlepdf.pdftools.structure_meta import TOOLS as STRUCTURE_META_TOOLS
from paddlepdf.pdftools.structure_ops import TOOLS as STRUCTURE_OPS_TOOLS

BASE_TOOLS: tuple[ToolSpec, ...] = (
    *PAGES_BASIC_TOOLS,
    *PAGES_GEOMETRY_TOOLS,
    *LAYOUT_TOOLS,
    *MARKING_TOOLS,
    *SECURITY_TOOLS,
    *SIGNATURES_TOOLS,
    *STRUCTURE_META_TOOLS,
    *STRUCTURE_OPS_TOOLS,
    *FORMS_TOOLS,
    *CREATE_TOOLS,
    *OFFICE_TOOLS,
)


def find_base_tool(name: str) -> ToolSpec | None:
    return next((spec for spec in BASE_TOOLS if spec.name == name), None)
