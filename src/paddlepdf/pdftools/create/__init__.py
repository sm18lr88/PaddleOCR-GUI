from paddlepdf.pdftools.contract import ToolSpec
from paddlepdf.pdftools.create.comics import pdf_comic_archive
from paddlepdf.pdftools.create.images import pdf_images_to_pdf
from paddlepdf.pdftools.create.json_document import json_to_pdf
from paddlepdf.pdftools.create.styled import (
    pdf_convert_excel,
    pdf_convert_html,
    pdf_convert_markdown,
)


def _describe(*sentence_parts: str) -> str:
    return " ".join(sentence_parts)


TOOLS: tuple[ToolSpec, ...] = (
    ToolSpec(
        "pdf_convert_html",
        _describe(
            "Render an HTML file to a styled PDF using a CSS preset (github, elegant,",
            "minimal, branded, compact), optional custom_css, page_size, orientation",
            "and margin_mm. Writes output_file.",
        ),
        pdf_convert_html,
    ),
    ToolSpec(
        "pdf_convert_markdown",
        _describe(
            "Render a Markdown file (tables, fenced code, footnotes) to a styled PDF",
            "with the same presets and page options as pdf_convert_html.",
            "Writes output_file.",
        ),
        pdf_convert_markdown,
    ),
    ToolSpec(
        "pdf_convert_excel",
        _describe(
            "Render every sheet of an .xlsx workbook, or a .csv, as styled HTML tables",
            "(first row as header) into a PDF. Writes output_file; data reports",
            "page_count and data_rows.",
        ),
        pdf_convert_excel,
    ),
    ToolSpec(
        "json_to_pdf",
        _describe(
            "Synthesize a PDF from PaperPilot's JSON document schema: one Letter page",
            "per JSON page with its text, plus base64 or file images drawn at their",
            "bbox. Writes output_file.",
        ),
        json_to_pdf,
    ),
    ToolSpec(
        "pdf_images_to_pdf",
        _describe(
            "Combine images into a PDF, one page per image in input order. Pages match",
            "each image's size, or a paper size with fit, orientation and margin_mm.",
        ),
        pdf_images_to_pdf,
    ),
    ToolSpec(
        "pdf_comic_archive",
        _describe(
            "Convert a PDF into a CBZ comic archive of rendered page images, or a",
            "CBZ/CBT archive into a PDF with images in natural filename order.",
            "CBR (RAR) is not supported.",
        ),
        pdf_comic_archive,
    ),
)
