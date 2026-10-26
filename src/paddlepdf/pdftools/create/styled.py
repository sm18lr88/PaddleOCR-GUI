"""HTML, Markdown, and Excel/CSV to styled PDF (PaperPilot preset stylesheets)."""

from pathlib import Path
from typing import Annotated, Final

import markdown
from pydantic import Field, JsonValue

from paddlepdf.pdftools.common import input_path, output_path
from paddlepdf.pdftools.contract import PdfToolError, ToolOutcome
from paddlepdf.pdftools.create.html_render import render_html
from paddlepdf.pdftools.create.spreadsheet import (
    SPREADSHEET_SUFFIXES,
    html_document,
    spreadsheet_html,
)
from paddlepdf.pdftools.create.styles import (
    Orientation,
    PageSize,
    PresetName,
    compose_css,
)
from paddlepdf.pdftools.pdfium import page_count

_MARKDOWN_EXTENSIONS: Final = ["extra", "sane_lists", "toc"]
_PRESETS: Final = (
    "github, elegant/academic, minimal/minimalist, branded/corporate, compact"
)
_PRESET_HELP: Final = f"Stylesheet preset (default github): {_PRESETS}."

OutputParam = Annotated[str, Field(description="Path of the PDF to write.")]
PresetParam = Annotated[PresetName, Field(description=_PRESET_HELP)]
CustomCssParam = Annotated[
    str | None,
    Field(description="Extra CSS appended after the preset; it overrides the preset."),
]
PageSizeParam = Annotated[PageSize, Field(description="Paper size.")]
OrientationParam = Annotated[Orientation, Field(description="Page orientation.")]
MarginParam = Annotated[
    float | None,
    Field(ge=0, le=100, description="Page margin in mm; default is the preset's."),
]


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError as error:
        msg = f"{path} is not UTF-8 text: {error}"
        raise PdfToolError(msg) from error


def _render(
    html: str,
    source: Path,
    target: Path,
    css: str,
    extra: dict[str, JsonValue] | None = None,
) -> ToolOutcome:
    warnings = render_html(html, css, source, target)
    data: dict[str, JsonValue] = {"page_count": page_count(target), **(extra or {})}
    return ToolOutcome(output_files=(str(target),), data=data, warnings=tuple(warnings))


def pdf_convert_html(
    input_file: Annotated[
        str,
        Field(description="HTML file; relative images resolve inside its folder."),
    ],
    output_file: OutputParam,
    preset: PresetParam = "github",
    custom_css: CustomCssParam = None,
    page_size: PageSizeParam = PageSize.A4,
    orientation: OrientationParam = "portrait",
    margin_mm: MarginParam = None,
) -> ToolOutcome:
    source = input_path(input_file, (".html", ".htm", ".xhtml"))
    target = output_path(output_file, source)
    css = compose_css(preset, custom_css, page_size, orientation, margin_mm)
    return _render(_read_text(source), source, target, css)


def pdf_convert_markdown(
    input_file: Annotated[
        str,
        Field(description="Markdown file; relative images resolve inside its folder."),
    ],
    output_file: OutputParam,
    preset: PresetParam = "github",
    custom_css: CustomCssParam = None,
    page_size: PageSizeParam = PageSize.A4,
    orientation: OrientationParam = "portrait",
    margin_mm: MarginParam = None,
) -> ToolOutcome:
    source = input_path(input_file, (".md", ".markdown", ".txt"))
    target = output_path(output_file, source)
    body = markdown.markdown(_read_text(source), extensions=_MARKDOWN_EXTENSIONS)
    css = compose_css(preset, custom_css, page_size, orientation, margin_mm)
    return _render(html_document(body), source, target, css)


def pdf_convert_excel(
    input_file: Annotated[
        str,
        Field(description="Spreadsheet (.xlsx/.xlsm/.xltx/.xltm) or .csv file."),
    ],
    output_file: OutputParam,
    preset: PresetParam = "github",
    custom_css: CustomCssParam = None,
    page_size: PageSizeParam = PageSize.A4,
    orientation: OrientationParam = "portrait",
    margin_mm: MarginParam = None,
) -> ToolOutcome:
    source = input_path(input_file, SPREADSHEET_SUFFIXES)
    target = output_path(output_file, source)
    html, rows = spreadsheet_html(source)
    css = compose_css(preset, custom_css, page_size, orientation, margin_mm)
    return _render(html, source, target, css, {"data_rows": rows})
