from collections.abc import Callable
from pathlib import Path

import pikepdf
import pytest
from reportlab.pdfgen.canvas import Canvas

from paddlepdf.pdftools import pdfium
from paddlepdf.pdftools.contract import ToolStatus
from paddlepdf.pdftools.pages_geometry import TOOLS
from paddlepdf.pdftools.runner import run_tool

type MakePdf = Callable[..., Path]

SPECS = {spec.name: spec for spec in TOOLS}


def _boxes(path: Path, key: str) -> list[list[float]]:
    with pikepdf.open(path) as pdf:
        return [[float(v) for v in page.obj[key]] for page in pdf.pages]


def test_tool_names() -> None:
    assert sorted(SPECS) == [
        "pdf_auto_rotate",
        "pdf_crop",
        "pdf_remove_blank",
        "pdf_scale_pages",
        "pdf_split_by_outline",
        "pdf_split_scanned_book",
    ]


def test_crop_sets_cropbox_on_selected_pages(make_pdf: MakePdf, tmp_path: Path) -> None:
    out = tmp_path / "cropped.pdf"
    result = run_tool(
        SPECS["pdf_crop"],
        {
            "input_file": str(make_pdf()),
            "output_file": str(out),
            "crop_box": "10,20,100,200",
            "pages": "1,3",
        },
    )
    assert result.status == ToolStatus.SUCCESS
    with pikepdf.open(out) as pdf:
        assert [("/CropBox" in p.obj) for p in pdf.pages] == [True, False, True]
        assert [float(v) for v in pdf.pages[0].obj["/CropBox"]] == [10, 20, 100, 200]


def test_crop_rejects_inverted_box(make_pdf: MakePdf, tmp_path: Path) -> None:
    result = run_tool(
        SPECS["pdf_crop"],
        {
            "input_file": str(make_pdf()),
            "output_file": str(tmp_path / "x.pdf"),
            "crop_box": "100,20,10,200",
        },
    )
    assert result.status == ToolStatus.FAILED
    assert result.errors


def test_scale_to_a4_keeps_content(make_pdf: MakePdf, tmp_path: Path) -> None:
    out = tmp_path / "a4.pdf"
    result = run_tool(
        SPECS["pdf_scale_pages"],
        {"input_file": str(make_pdf(pages=2)), "output_file": str(out)},
    )
    assert result.status == ToolStatus.SUCCESS
    for box in _boxes(out, "/MediaBox"):
        assert box == pytest.approx([0, 0, 595.28, 841.89])
    assert pdfium.page_texts(out)[1].strip() == "Page 2"


def test_scale_original_half(make_pdf: MakePdf, tmp_path: Path) -> None:
    out = tmp_path / "half.pdf"
    result = run_tool(
        SPECS["pdf_scale_pages"],
        {
            "input_file": str(make_pdf(pages=1)),
            "output_file": str(out),
            "target_size": "ORIGINAL",
            "scale_factor": 0.5,
        },
    )
    assert result.status == ToolStatus.SUCCESS
    assert _boxes(out, "/MediaBox")[0] == pytest.approx([0, 0, 306, 396])


def test_remove_blank_drops_empty_pages(tmp_path: Path) -> None:
    source = tmp_path / "mixed.pdf"
    canvas = Canvas(str(source))
    for label in ("keep one", None, "keep two"):
        if label:
            canvas.drawString(72, 700, label)
        canvas.showPage()
    canvas.save()
    out = tmp_path / "clean.pdf"
    result = run_tool(
        SPECS["pdf_remove_blank"],
        {"input_file": str(source), "output_file": str(out)},
    )
    assert result.status == ToolStatus.SUCCESS
    assert result.data == {"removed_pages": [2], "remaining": 2}
    assert [t.strip() for t in pdfium.page_texts(out)] == ["keep one", "keep two"]


def test_remove_blank_all_blank_fails(tmp_path: Path) -> None:
    source = tmp_path / "blank.pdf"
    canvas = Canvas(str(source))
    canvas.showPage()
    canvas.save()
    result = run_tool(
        SPECS["pdf_remove_blank"],
        {"input_file": str(source), "output_file": str(tmp_path / "o.pdf")},
    )
    assert result.status == ToolStatus.FAILED
    assert result.errors


def test_split_by_outline_writes_chapters(make_pdf: MakePdf, tmp_path: Path) -> None:
    source = make_pdf(pages=5)
    bookmarked = tmp_path / "book.pdf"
    with pikepdf.open(source) as pdf:
        with pdf.open_outline() as outline:
            outline.root.append(pikepdf.OutlineItem("Intro: Start", 0))
            outline.root.append(pikepdf.OutlineItem("Part 2", 2))
        pdf.save(bookmarked)
    out_dir = tmp_path / "chapters"
    result = run_tool(
        SPECS["pdf_split_by_outline"],
        {"input_file": str(bookmarked), "output_dir": str(out_dir), "create_zip": True},
    )
    assert result.status == ToolStatus.SUCCESS
    names = sorted(Path(f).name for f in result.output_files)
    assert names == ["01_Intro_ Start.pdf", "02_Part 2.pdf", "chapters.zip"]
    assert pdfium.page_texts(out_dir / "01_Intro_ Start.pdf")[0].strip() == "Page 1"
    assert pdfium.page_count(out_dir / "02_Part 2.pdf") == 3


def test_split_by_outline_without_bookmarks_fails(
    make_pdf: MakePdf, tmp_path: Path
) -> None:
    result = run_tool(
        SPECS["pdf_split_by_outline"],
        {"input_file": str(make_pdf()), "output_dir": str(tmp_path / "o")},
    )
    assert result.status == ToolStatus.FAILED
    assert result.errors


@pytest.mark.parametrize(
    ("options", "expected"),
    [
        ({}, [[0, 0, 500, 500], [500, 0, 1000, 500]]),
        ({"reading_direction": "rtl"}, [[500, 0, 1000, 500], [0, 0, 500, 500]]),
        ({"gutter_overlap": 10}, [[0, 0, 510, 500], [490, 0, 1000, 500]]),
        (
            {"split_horizontal": True},
            [[0, 250, 1000, 500], [0, 0, 1000, 250]],
        ),
    ],
)
def test_split_scanned_book_orders_halves(
    make_pdf: MakePdf,
    tmp_path: Path,
    options: dict[str, object],
    expected: list[list[float]],
) -> None:
    out = tmp_path / "split.pdf"
    result = run_tool(
        SPECS["pdf_split_scanned_book"],
        {
            "input_file": str(make_pdf(pages=1, size=(1000, 500))),
            "output_file": str(out),
            **options,
        },
    )
    assert result.status == ToolStatus.SUCCESS
    assert _boxes(out, "/MediaBox") == expected


def test_auto_rotate_landscape_to_portrait(make_pdf: MakePdf, tmp_path: Path) -> None:
    out = tmp_path / "rot.pdf"
    result = run_tool(
        SPECS["pdf_auto_rotate"],
        {
            "input_file": str(make_pdf(pages=2, size=(842, 595))),
            "output_file": str(out),
            "pages": "1",
        },
    )
    assert result.status == ToolStatus.SUCCESS
    with pikepdf.open(out) as pdf:
        assert int(pdf.pages[0].obj["/Rotate"]) == 90
        assert int(pdf.pages[1].obj.get("/Rotate", 0)) == 0


def test_auto_rotate_leaves_portrait_alone(make_pdf: MakePdf, tmp_path: Path) -> None:
    out = tmp_path / "same.pdf"
    result = run_tool(
        SPECS["pdf_auto_rotate"],
        {"input_file": str(make_pdf(pages=1)), "output_file": str(out)},
    )
    assert result.data == {"rotated_pages": {}}
    with pikepdf.open(out) as pdf:
        assert int(pdf.pages[0].obj.get("/Rotate", 0)) == 0
