import base64
from collections.abc import Callable
from io import BytesIO
from pathlib import Path

import pikepdf
from PIL import Image

from paddlepdf.pdftools import pdfium
from paddlepdf.pdftools.contract import ToolSpec, ToolStatus
from paddlepdf.pdftools.marking import TOOLS
from paddlepdf.pdftools.marking.numbering import (
    pdf_bates,
    pdf_header_footer,
    pdf_page_numbers,
)
from paddlepdf.pdftools.marking.stamp import pdf_stamp
from paddlepdf.pdftools.marking.watermark import pdf_watermark
from paddlepdf.pdftools.runner import run_tool

type MakePdf = Callable[..., Path]

DPI_SCALE = 150 / 72


def _spec(handler_name: str) -> ToolSpec:
    return next(spec for spec in TOOLS if spec.handler.__name__ == handler_name)


def _png(path: Path, color: tuple[int, int, int, int]) -> Path:
    Image.new("RGBA", (40, 20), color).save(path)
    return path


def _pixel(
    path: Path, page: int, x_pt: float, y_pt_from_bottom: float
) -> tuple[int, ...]:
    image = pdfium.render_page(path, page).convert("RGB")
    px = int(x_pt * DPI_SCALE)
    py = image.height - int(y_pt_from_bottom * DPI_SCALE)
    return tuple(image.crop((px, py, px + 1, py + 1)).tobytes())


def test_registry_names() -> None:
    assert sorted(spec.name for spec in TOOLS) == [
        "pdf_annotate",
        "pdf_bates",
        "pdf_header_footer",
        "pdf_page_numbers",
        "pdf_stamp",
        "pdf_timestamp",
        "pdf_watermark",
    ]


def test_watermark_text_on_selected_pages(make_pdf: MakePdf, tmp_path: Path) -> None:
    source = make_pdf()
    target = tmp_path / "wm.pdf"
    result = run_tool(
        _spec(pdf_watermark.__name__),
        {
            "input_file": str(source),
            "output_file": str(target),
            "text": "CONFIDENTIAL",
            "pages": "2",
            "opacity": 0.5,
        },
    )
    assert result.status is ToolStatus.SUCCESS, result.errors
    assert result.output_files == (str(target),)
    texts = pdfium.page_texts(target)
    assert "CONFIDENTIAL" not in texts[0]
    assert "CONFIDENTIAL" in texts[1]
    assert "Page 2" in texts[1]


def test_watermark_image_renders_and_text_free_input_fails(
    make_pdf: MakePdf, tmp_path: Path
) -> None:
    source = make_pdf(pages=1)
    logo = _png(tmp_path / "logo.png", (255, 0, 0, 255))
    target = tmp_path / "wm_image.pdf"
    result = run_tool(
        _spec(pdf_watermark.__name__),
        {
            "input_file": str(source),
            "output_file": str(target),
            "image_file": str(logo),
            "opacity": 1.0,
            "angle": 0,
            "image_scale": 0.5,
        },
    )
    assert result.status is ToolStatus.SUCCESS, result.errors
    red, green, blue = _pixel(target, 0, 306, 396)[:3]
    assert red > 200
    assert green < 60
    assert blue < 60
    empty = run_tool(
        _spec(pdf_watermark.__name__),
        {"input_file": str(source), "output_file": str(tmp_path / "x.pdf")},
    )
    assert empty.status is ToolStatus.FAILED
    assert empty.errors


def test_stamp_from_file_and_base64(make_pdf: MakePdf, tmp_path: Path) -> None:
    source = make_pdf(pages=2)
    logo = _png(tmp_path / "logo.png", (0, 0, 255, 255))
    by_file = tmp_path / "stamp_file.pdf"
    first = run_tool(
        _spec(pdf_stamp.__name__),
        {
            "input_file": str(source),
            "output_file": str(by_file),
            "image_file": str(logo),
            "x": 100,
            "y": 100,
            "width": 100,
            "height": 50,
            "pages": "last",
        },
    )
    assert first.status is ToolStatus.SUCCESS, first.errors
    assert _pixel(by_file, 1, 150, 125)[2] > 200
    assert _pixel(by_file, 0, 150, 125) == (255, 255, 255)
    buffer = BytesIO()
    Image.new("RGB", (8, 8), (0, 255, 0)).save(buffer, format="PNG")
    by_data = tmp_path / "stamp_data.pdf"
    second = run_tool(
        _spec(pdf_stamp.__name__),
        {
            "input_file": str(source),
            "output_file": str(by_data),
            "image_base64": base64.b64encode(buffer.getvalue()).decode(),
            "x": 100,
            "y": 100,
            "width": 100,
            "height": 50,
        },
    )
    assert second.status is ToolStatus.SUCCESS, second.errors
    assert _pixel(by_data, 0, 150, 125)[1] > 200


def test_stamp_requires_an_image(make_pdf: MakePdf, tmp_path: Path) -> None:
    result = run_tool(
        _spec(pdf_stamp.__name__),
        {"input_file": str(make_pdf()), "output_file": str(tmp_path / "o.pdf")},
    )
    assert result.status is ToolStatus.FAILED
    assert result.errors


def test_page_numbers_default_and_custom(make_pdf: MakePdf, tmp_path: Path) -> None:
    source = make_pdf()
    default = tmp_path / "numbers.pdf"
    result = run_tool(
        _spec(pdf_page_numbers.__name__),
        {"input_file": str(source), "output_file": str(default)},
    )
    assert result.status is ToolStatus.SUCCESS, result.errors
    for number, text in enumerate(pdfium.page_texts(default), start=1):
        assert f"Page {number} of 3" in text
    custom = tmp_path / "numbers_custom.pdf"
    run_tool(
        _spec(pdf_page_numbers.__name__),
        {
            "input_file": str(source),
            "output_file": str(custom),
            "label_format": "<{n}/{total}>",
            "start_number": 10,
            "position": "top-center",
            "pages": "2-3",
        },
    )
    texts = pdfium.page_texts(custom)
    assert "<10/3>" not in texts[0]
    assert "<11/3>" in texts[1]
    assert "<12/3>" in texts[2]


def test_page_numbers_follow_page_rotation(make_pdf: MakePdf, tmp_path: Path) -> None:
    source = make_pdf(pages=1)
    with pikepdf.open(source, allow_overwriting_input=True) as pdf:
        pdf.pages[0].Rotate = 90
        pdf.save(source)
    target = tmp_path / "rotated.pdf"
    result = run_tool(
        _spec(pdf_page_numbers.__name__),
        {
            "input_file": str(source),
            "output_file": str(target),
            "label_format": "ROTATED",
            "position": "bottom-right",
        },
    )
    assert result.status is ToolStatus.SUCCESS, result.errors
    assert "ROTATED" in pdfium.page_texts(target)[0]
    image = pdfium.render_page(source, 0).convert("L")
    marked = pdfium.render_page(target, 0).convert("L")
    region = (
        int(image.width * 0.75),
        int(image.height * 0.85),
        image.width,
        image.height,
    )
    assert min(image.crop(region).tobytes()) == 255
    assert min(marked.crop(region).tobytes()) < 128


def test_header_and_footer_text(make_pdf: MakePdf, tmp_path: Path) -> None:
    source = make_pdf(pages=2)
    header = tmp_path / "header.pdf"
    footer = tmp_path / "footer.pdf"
    first = run_tool(
        _spec(pdf_header_footer.__name__),
        {"input_file": str(source), "output_file": str(header), "text": "TOP SECRET"},
    )
    second = run_tool(
        _spec(pdf_header_footer.__name__),
        {
            "input_file": str(source),
            "output_file": str(footer),
            "text": "Footer {n}/{total}",
            "position": "bottom-center",
        },
    )
    assert first.status is ToolStatus.SUCCESS, first.errors
    assert second.status is ToolStatus.SUCCESS, second.errors
    assert all("TOP SECRET" in text for text in pdfium.page_texts(header))
    assert "Footer 2/2" in pdfium.page_texts(footer)[1]
    boxes = pdfium.find_text_boxes(header, "TOP SECRET")
    assert boxes[0][0][1] > 700


def test_bates_numbers_each_page(make_pdf: MakePdf, tmp_path: Path) -> None:
    target = tmp_path / "bates.pdf"
    result = run_tool(
        _spec(pdf_bates.__name__),
        {
            "input_file": str(make_pdf()),
            "output_file": str(target),
            "prefix": "ACME-",
            "start_number": 5,
            "padding": 6,
        },
    )
    assert result.status is ToolStatus.SUCCESS, result.errors
    texts = pdfium.page_texts(target)
    assert [f"ACME-{n:06d}" in texts[i] for i, n in enumerate((5, 6, 7))] == [True] * 3


def test_overlay_tools_fail_on_missing_input_and_bad_pages(
    make_pdf: MakePdf, tmp_path: Path
) -> None:
    missing = run_tool(
        _spec(pdf_bates.__name__),
        {
            "input_file": str(tmp_path / "nope.pdf"),
            "output_file": str(tmp_path / "o.pdf"),
        },
    )
    assert missing.status is ToolStatus.FAILED
    assert missing.errors
    bad_pages = run_tool(
        _spec(pdf_header_footer.__name__),
        {
            "input_file": str(make_pdf()),
            "output_file": str(tmp_path / "o.pdf"),
            "text": "x",
            "pages": "9",
        },
    )
    assert bad_pages.status is ToolStatus.FAILED
    assert bad_pages.errors
