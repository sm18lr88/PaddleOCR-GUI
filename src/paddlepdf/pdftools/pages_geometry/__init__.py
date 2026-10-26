from paddlepdf.pdftools.contract import ToolSpec
from paddlepdf.pdftools.pages_geometry.blank import pdf_remove_blank
from paddlepdf.pdftools.pages_geometry.geometry import (
    pdf_auto_rotate,
    pdf_crop,
    pdf_scale_pages,
)
from paddlepdf.pdftools.pages_geometry.split import (
    pdf_split_by_outline,
    pdf_split_scanned_book,
)


def _describe(text: str) -> str:
    return " ".join(text.split())


TOOLS: tuple[ToolSpec, ...] = (
    ToolSpec(
        "pdf_crop",
        _describe(
            """Crop selected pages by setting the CropBox to
            'left,bottom,right,top' (PDF points). Writes a new PDF."""
        ),
        pdf_crop,
    ),
    ToolSpec(
        "pdf_scale_pages",
        _describe(
            """Scale page content and MediaBox to a standard paper size
            (A3/A4/A5/LETTER/LEGAL/TABLOID) or by a factor, optionally keeping
            aspect ratio and centering."""
        ),
        pdf_scale_pages,
    ),
    ToolSpec(
        "pdf_remove_blank",
        _describe(
            """Remove pages without text, images, or meaningful content;
            sensitivity 0-100 (default 95). Writes a new PDF and lists removed
            pages."""
        ),
        pdf_remove_blank,
    ),
    ToolSpec(
        "pdf_split_by_outline",
        _describe(
            """Split a PDF into per-chapter PDFs (NN_Title.pdf) in output_dir using
            its bookmarks down to max_depth, optionally also chapters.zip."""
        ),
        pdf_split_by_outline,
    ),
    ToolSpec(
        "pdf_split_scanned_book",
        _describe(
            """Split two-up scanned spreads into two pages each (left/right or
            top/bottom) with optional gutter overlap and ltr/rtl order."""
        ),
        pdf_split_scanned_book,
    ),
    ToolSpec(
        "pdf_auto_rotate",
        _describe(
            """Rotate pages 90 degrees when their MediaBox shape does not match
            the target orientation (portrait, landscape, auto = portrait)."""
        ),
        pdf_auto_rotate,
    ),
)
