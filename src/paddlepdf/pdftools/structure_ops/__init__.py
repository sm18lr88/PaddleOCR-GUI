from paddlepdf.pdftools.contract import ToolSpec
from paddlepdf.pdftools.structure_ops.compare import pdf_compare
from paddlepdf.pdftools.structure_ops.compress import pdf_compress
from paddlepdf.pdftools.structure_ops.images import pdf_extract_images, pdf_render
from paddlepdf.pdftools.structure_ops.pdf_a import pdf_to_pdf_a
from paddlepdf.pdftools.structure_ops.rewrite import (
    pdf_flatten,
    pdf_linearize,
    pdf_repair,
)

TOOLS: tuple[ToolSpec, ...] = (
    ToolSpec(
        "pdf_repair",
        (
            "Repair a damaged PDF (broken xref/offsets) by recovering its objects and "
            "rewriting a clean file to output_file; data lists problems found and left."
        ),
        pdf_repair,
    ),
    ToolSpec(
        "pdf_linearize",
        (
            "Linearize a PDF for fast web view (page-at-a-time loading) and save it to "
            "output_file; data.linearized confirms the result."
        ),
        pdf_linearize,
    ),
    ToolSpec(
        "pdf_flatten",
        (
            "Flatten form fields and annotations into static page content (mode "
            "all/print/screen) and drop the interactive form; writes output_file."
        ),
        pdf_flatten,
    ),
    ToolSpec(
        "pdf_to_pdf_a",
        (
            "Best-effort PDF/A-2b conversion: adds pdfaid XMP and an sRGB OutputIntent,"
            " removes JavaScript/forbidden actions and encryption. Conformance is NOT "
            "validated; warnings list known blockers such as unembedded fonts."
        ),
        pdf_to_pdf_a,
    ),
    ToolSpec(
        "pdf_compress",
        (
            "Shrink a PDF: recompress plain RGB/gray raster images to JPEG (quality "
            "low/medium/high or 1-100, downscaled to a size cap) and pack object "
            "streams. Never grows the file; data reports original and output sizes."
        ),
        pdf_compress,
    ),
    ToolSpec(
        "pdf_extract_images",
        (
            "Extract embedded raster images from the selected pages into output_dir "
            "(JPEG/JPEG2000 passed through, others as PNG/TIFF); data lists each image."
        ),
        pdf_extract_images,
    ),
    ToolSpec(
        "pdf_render",
        (
            "Render selected pages (default page 1) to PNG or JPEG files in output_dir "
            "at the given dpi; data lists each page's file and pixel size."
        ),
        pdf_render,
    ),
    ToolSpec(
        "pdf_compare",
        (
            "Compare two PDFs page by page: unified text diffs in data, optional JSON "
            "report (output_file) and red-highlighted visual diff PNGs (visual_diff + "
            "output_dir)."
        ),
        pdf_compare,
    ),
)
