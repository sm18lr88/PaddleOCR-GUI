from paddlepdf.pdftools.contract import ToolSpec
from paddlepdf.pdftools.pages_basic.selection import (
    pdf_delete_pages,
    pdf_extract_pages,
    pdf_reorder_pages,
    pdf_rotate,
)
from paddlepdf.pdftools.pages_basic.splitting import pdf_burst, pdf_merge, pdf_split

TOOLS: tuple[ToolSpec, ...] = (
    ToolSpec(
        "pdf_merge",
        "Merge 2+ PDFs into one in the given file and page order.",
        pdf_merge,
    ),
    ToolSpec(
        "pdf_split",
        "Split a PDF by 'every' N pages or 'split_after' cuts into <stem>-N.pdf.",
        pdf_split,
    ),
    ToolSpec(
        "pdf_burst",
        "Burst a PDF into single-page PDFs named <stem>-N.pdf in output_dir.",
        pdf_burst,
    ),
    ToolSpec(
        "pdf_extract_pages",
        "Keep only the listed 1-based pages (e.g. 1,3-5,last) in a new PDF.",
        pdf_extract_pages,
    ),
    ToolSpec(
        "pdf_delete_pages",
        "Delete the listed 1-based pages and write the rest to output_file.",
        pdf_delete_pages,
    ),
    ToolSpec(
        "pdf_reorder_pages",
        "Reorder pages by a complete 1-based order list such as 3,1,2.",
        pdf_reorder_pages,
    ),
    ToolSpec(
        "pdf_rotate",
        "Rotate pages clockwise by a multiple of 90, added to existing /Rotate.",
        pdf_rotate,
    ),
)
