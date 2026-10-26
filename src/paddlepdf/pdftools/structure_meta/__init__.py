from paddlepdf.pdftools.contract import ToolSpec
from paddlepdf.pdftools.structure_meta.attachments import pdf_attachments
from paddlepdf.pdftools.structure_meta.bookmarks import pdf_bookmarks
from paddlepdf.pdftools.structure_meta.classify import pdf_classify_type
from paddlepdf.pdftools.structure_meta.info_meta import pdf_info, pdf_metadata
from paddlepdf.pdftools.structure_meta.validate import pdf_validate

TOOLS: tuple[ToolSpec, ...] = (
    ToolSpec(
        "pdf_info",
        "Get basic PDF facts (page_count, version, encrypted, file size) as JSON data.",
        pdf_info,
    ),
    ToolSpec(
        "pdf_metadata",
        (
            "Read Info-dictionary/XMP metadata; set title/author/subject/keywords "
            "by giving fields plus output_file (writes a new PDF)."
        ),
        pdf_metadata,
    ),
    ToolSpec(
        "pdf_bookmarks",
        (
            "List the bookmark outline (action=list) or replace/append/clear it "
            "(set/add/clear) from [{title, page, children}], writing output_file."
        ),
        pdf_bookmarks,
    ),
    ToolSpec(
        "pdf_attachments",
        (
            "List, add (file_data_base64 or source_file), extract, or remove embedded "
            "attachments; add/remove write output_file, extract writes the bytes there."
        ),
        pdf_attachments,
    ),
    ToolSpec(
        "pdf_validate",
        (
            "Validate PDF structure (qpdf syntax check plus page count); "
            "data.is_valid and data.problems report the findings."
        ),
        pdf_validate,
    ),
    ToolSpec(
        "pdf_classify_type",
        (
            "Classify the document type by keywords (Invoice, Contract, Research "
            "Paper, Form) and detect digital vs scanned vs mixed pages."
        ),
        pdf_classify_type,
    ),
)
