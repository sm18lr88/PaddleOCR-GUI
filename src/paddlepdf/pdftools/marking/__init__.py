from paddlepdf.pdftools.contract import ToolSpec
from paddlepdf.pdftools.marking.annotate import pdf_annotate
from paddlepdf.pdftools.marking.numbering import (
    pdf_bates,
    pdf_header_footer,
    pdf_page_numbers,
)
from paddlepdf.pdftools.marking.stamp import pdf_stamp
from paddlepdf.pdftools.marking.timestamp import pdf_timestamp
from paddlepdf.pdftools.marking.watermark import pdf_watermark

TOOLS: tuple[ToolSpec, ...] = (
    ToolSpec(
        "pdf_watermark",
        "Overlay a text or image watermark (opacity, angle, pages) on a PDF.",
        pdf_watermark,
    ),
    ToolSpec(
        "pdf_stamp",
        "Place an image or logo at x, y, width, height on chosen PDF pages.",
        pdf_stamp,
    ),
    ToolSpec(
        "pdf_page_numbers",
        'Add page numbers from a "Page {n} of {total}" template to a PDF.',
        pdf_page_numbers,
    ),
    ToolSpec(
        "pdf_header_footer",
        "Draw header or footer text at a top/bottom position on PDF pages.",
        pdf_header_footer,
    ),
    ToolSpec(
        "pdf_bates",
        "Stamp Bates labels (prefix, start, padding, position) on each PDF page.",
        pdf_bates,
    ),
    ToolSpec(
        "pdf_timestamp",
        "Add an RFC 3161 TSA timestamp (tsa_url, needs network) to a PDF.",
        pdf_timestamp,
    ),
    ToolSpec(
        "pdf_annotate",
        "Add real PDF annotations: highlight, underline, strikethrough, note, pen.",
        pdf_annotate,
    ),
)
