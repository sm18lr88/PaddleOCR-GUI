"""PaperPilot CSS presets and page-size options, adapted to what xhtml2pdf renders."""

from enum import StrEnum
from typing import Final, Literal

type PresetName = Literal[
    "github",
    "elegant",
    "academic",
    "minimal",
    "minimalist",
    "branded",
    "corporate",
    "compact",
]
type Orientation = Literal["portrait", "landscape"]


class PageSize(StrEnum):
    A3 = "A3"
    A4 = "A4"
    A5 = "A5"
    LETTER = "Letter"
    LEGAL = "Legal"


_GITHUB: Final = """
body { font-family: Helvetica, sans-serif; font-size: 10.5pt; line-height: 1.6;
  color: #24292e; }
h1, h2, h3, h4, h5, h6 { margin-top: 18pt; margin-bottom: 12pt; font-weight: bold;
  line-height: 1.25; color: #1f2328; }
h1 { font-size: 21pt; border-bottom: 1px solid #eaecef; padding-bottom: 4pt; }
h2 { font-size: 15.75pt; border-bottom: 1px solid #eaecef; padding-bottom: 3pt; }
code { background-color: #eceef0; font-family: Courier, monospace; font-size: 9pt; }
pre { background-color: #f6f8fa; padding: 12pt; line-height: 1.45;
  font-family: Courier, monospace; font-size: 9pt; }
table { width: 100%; margin: 12pt 0; }
th, td { padding: 6pt 9pt; border: 1px solid #d0d7de; }
th { background-color: #f6f8fa; font-weight: bold; }
"""

_ELEGANT: Final = """
body { font-family: Times, serif; font-size: 11.25pt; line-height: 1.7;
  color: #2c3e50; }
h1, h2, h3 { font-family: Times, serif; color: #1a252f; }
h1 { font-size: 24.75pt; text-align: center; margin-bottom: 18pt; }
h2 { font-size: 18pt; border-bottom: 2px solid #8e44ad; padding-bottom: 4pt;
  margin-top: 20pt; }
table { width: 100%; margin: 15pt 0; }
th { border-bottom: 2px solid #2c3e50; padding: 7pt 10pt; font-size: 10.5pt;
  text-transform: uppercase; }
td { border-bottom: 1px solid #ecf0f1; padding: 7pt 10pt; }
"""

_MINIMAL: Final = """
body { font-family: Helvetica, sans-serif; font-size: 9.75pt; line-height: 1.5;
  color: #111111; }
h1, h2, h3 { font-weight: bold; color: #000000; }
h1 { font-size: 17.5pt; }
h2 { font-size: 13.65pt; }
table { width: 100%; margin: 12pt 0; }
th, td { padding: 4pt 7pt; border-bottom: 1px solid #000000; text-align: left; }
th { font-weight: bold; border-top: 1px solid #000000; }
"""

_BRANDED: Final = """
body { font-family: Helvetica, sans-serif; font-size: 10pt; line-height: 1.6;
  color: #1e293b; }
h1 { font-size: 20pt; color: #4361ee; border-left: 4px solid #4361ee;
  padding-left: 9pt; }
h2 { font-size: 14pt; color: #3a0ca3; margin-top: 15pt; }
table { width: 100%; border: 1px solid #e2e8f0; margin: 12pt 0; }
th { background-color: #4361ee; color: #ffffff; padding: 7pt 10pt; font-weight: bold;
  text-align: left; }
td { padding: 6pt 10pt; border-bottom: 1px solid #f1f5f9; }
"""

_COMPACT: Final = """
body { font-family: Helvetica, sans-serif; font-size: 8.25pt; line-height: 1.35;
  color: #1f2937; }
h1 { font-size: 11.5pt; margin-bottom: 6pt; }
h2 { font-size: 9.9pt; margin-top: 9pt; margin-bottom: 4pt; }
table { width: 100%; margin: 6pt 0; font-size: 7.9pt; }
th, td { padding: 3pt 4pt; border: 1px solid #d1d5db; }
th { background-color: #f3f4f6; font-weight: bold; }
"""

_PRESETS: Final[dict[str, tuple[str, float]]] = {
    "github": (_GITHUB, 20),
    "elegant": (_ELEGANT, 25),
    "academic": (_ELEGANT, 25),
    "minimal": (_MINIMAL, 18),
    "minimalist": (_MINIMAL, 18),
    "branded": (_BRANDED, 20),
    "corporate": (_BRANDED, 20),
    "compact": (_COMPACT, 12),
}


def compose_css(
    preset: PresetName,
    custom_css: str | None,
    page_size: PageSize,
    orientation: Orientation,
    margin_mm: float | None,
) -> str:
    """Return the @page rule, the preset stylesheet, then custom CSS (which wins)."""
    body_css, preset_margin = _PRESETS[preset]
    margin = preset_margin if margin_mm is None else margin_mm
    size = page_size.value.lower()
    if orientation == "landscape":
        size = f"{size} landscape"
    parts = [f"@page {{ size: {size}; margin: {margin}mm; }}", body_css]
    if custom_css and custom_css.strip():
        parts.extend(("/* Custom CSS */", custom_css))
    return "\n".join(parts)
