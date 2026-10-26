from paddlepdf.pdftools.contract import ToolSpec
from paddlepdf.pdftools.layout.booklet import pdf_booklet
from paddlepdf.pdftools.layout.invert import pdf_invert_colors
from paddlepdf.pdftools.layout.nup import pdf_nup
from paddlepdf.pdftools.layout.overlay import pdf_overlay_underlay
from paddlepdf.pdftools.layout.stitch import pdf_stitch_canvas

TOOLS: tuple[ToolSpec, ...] = (
    ToolSpec(
        "pdf_booklet",
        "Reorder pages into booklet order, as 2-up fold sheets or single pages.",
        pdf_booklet,
    ),
    ToolSpec(
        "pdf_nup",
        "Place 2, 4, 9, or 16 pages per sheet in a grid; outputs one PDF.",
        pdf_nup,
    ),
    ToolSpec(
        "pdf_stitch_canvas",
        "Join all pages into one continuous page, vertical or horizontal.",
        pdf_stitch_canvas,
    ),
    ToolSpec(
        "pdf_overlay_underlay",
        "Stamp page 1 of a template PDF behind or over pages, with opacity.",
        pdf_overlay_underlay,
    ),
    ToolSpec(
        "pdf_invert_colors",
        "Recolor pages (dark_mode, true_invert, high_contrast, sepia).",
        pdf_invert_colors,
    ),
)
