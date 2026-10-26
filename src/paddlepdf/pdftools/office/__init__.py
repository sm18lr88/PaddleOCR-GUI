from paddlepdf.pdftools.contract import ToolSpec
from paddlepdf.pdftools.office.documents import (
    office_extract_text,
    office_modernize_legacy,
    office_to_markdown,
)
from paddlepdf.pdftools.office.pdf_export import pdf_to_docx, pdf_to_pptx
from paddlepdf.pdftools.office.pdf_tables import pdf_to_xlsx
from paddlepdf.pdftools.office.spreadsheets import excel_to_csv, excel_to_json


def _describe(*sentence_parts: str) -> str:
    return " ".join(sentence_parts)


TOOLS: tuple[ToolSpec, ...] = (
    ToolSpec(
        "pdf_to_docx",
        _describe(
            "Convert a PDF to an editable Word .docx: one paragraph per text line, a",
            "page break between pages, and each page's embedded images",
            "(include_images).",
        ),
        pdf_to_docx,
    ),
    ToolSpec(
        "pdf_to_xlsx",
        _describe(
            "Convert a PDF to an Excel .xlsx with one sheet per page; detected",
            "tables are split into rows/columns by word position, other pages",
            "list their text lines.",
        ),
        pdf_to_xlsx,
    ),
    ToolSpec(
        "pdf_to_pptx",
        _describe(
            "Convert a PDF to a PowerPoint .pptx with one slide per page showing the",
            "page rendered at dpi, and the page text in the slide notes.",
        ),
        pdf_to_pptx,
    ),
    ToolSpec(
        "office_to_markdown",
        _describe(
            "Convert a .docx, .pptx, or .xlsx file to Markdown (headings, lists,",
            "tables, one section per slide or sheet) and write it to output_file.",
        ),
        office_to_markdown,
    ),
    ToolSpec(
        "office_extract_text",
        _describe(
            "Extract plain text from a .docx, .pptx, or .xlsx file into output_file",
            "(table rows are tab-separated).",
        ),
        office_extract_text,
    ),
    ToolSpec(
        "office_modernize_legacy",
        _describe(
            "Give a legacy-named Office file (.doc/.xls/.ppt) its modern",
            ".docx/.xlsx/.pptx form; fails with guidance for true OLE2 binaries,",
            "which cannot be read here.",
        ),
        office_modernize_legacy,
    ),
    ToolSpec(
        "excel_to_json",
        _describe(
            "Read Excel sheets (all, or one via sheet) into JSON: per sheet name,",
            "rows_count, columns, and data rows (objects when has_headers);",
            "optionally also saved to output_file.",
        ),
        excel_to_json,
    ),
    ToolSpec(
        "excel_to_csv",
        _describe(
            "Export an Excel sheet to RFC 4180 CSV; without sheet, multi-sheet",
            "workbooks also get one <stem>_<sheet>.csv per sheet.",
        ),
        excel_to_csv,
    ),
)
