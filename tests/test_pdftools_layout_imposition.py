from collections.abc import Callable
from pathlib import Path

import pikepdf
import pytest

from paddlepdf.pdftools.contract import ToolResult, ToolSpec, ToolStatus
from paddlepdf.pdftools.layout import TOOLS
from paddlepdf.pdftools.layout.booklet import booklet_sequence
from paddlepdf.pdftools.pdfium import page_texts
from paddlepdf.pdftools.runner import run_tool

type MakePdf = Callable[..., Path]

SPECS: dict[str, ToolSpec] = {spec.name: spec for spec in TOOLS}


def run(name: str, **params: object) -> ToolResult:
    return run_tool(SPECS[name], params)


def media_box(path: Path, index: int = 0) -> list[float]:
    with pikepdf.open(path) as pdf:
        return [float(v) for v in pdf.pages[index].mediabox]


def placements(path: Path, index: int = 0) -> list[tuple[float, float, float]]:
    """(scale, x, y) of every form drawn on a sheet."""
    with pikepdf.open(path) as pdf:
        found: list[tuple[float, float, float]] = []
        for operands, operator in pikepdf.parse_content_stream(pdf.pages[index]):
            if str(operator) == "cm":
                values = [float(v) for v in operands]
                found.append((values[0], values[4], values[5]))
        return found


def test_booklet_sequence_pads_to_multiple_of_four() -> None:
    assert booklet_sequence(5) == [8, 1, 2, 7, 6, 3, 4, 5]
    assert booklet_sequence(4) == [4, 1, 2, 3]


def test_booklet_reorders_single_pages(make_pdf: MakePdf, tmp_path: Path) -> None:
    source = make_pdf(pages=5)
    out = tmp_path / "booklet.pdf"
    result = run(
        "pdf_booklet", input_file=str(source), output_file=str(out), create_sheets=False
    )
    assert result.status == ToolStatus.SUCCESS
    assert result.output_files == (str(out),)
    texts = page_texts(out)
    assert len(texts) == 8
    expected = ["", "Page 1", "Page 2", "", "", "Page 3", "Page 4", "Page 5"]
    assert [t.strip() for t in texts] == expected


def test_booklet_sheets_place_spreads_with_gutter(
    make_pdf: MakePdf, tmp_path: Path
) -> None:
    source = make_pdf(pages=4)
    out = tmp_path / "sheets.pdf"
    result = run(
        "pdf_booklet",
        input_file=str(source),
        output_file=str(out),
        gutter_pt=20,
        center_fold_line=True,
    )
    assert result.status == ToolStatus.SUCCESS
    assert media_box(out) == [0, 0, 612 * 2 + 20, 792]
    texts = page_texts(out)
    assert len(texts) == 2
    assert "Page 4" in texts[0]
    assert "Page 1" in texts[0]
    assert "Page 2" in texts[1]
    assert "Page 3" in texts[1]
    with pikepdf.open(out) as pdf:
        assert b"[3 3] 0 d" in pdf.pages[0].Contents.read_bytes()


def test_nup_four_up_groups_pages_and_keeps_text(
    make_pdf: MakePdf, tmp_path: Path
) -> None:
    source = make_pdf(pages=5)
    out = tmp_path / "nup.pdf"
    result = run(
        "pdf_nup",
        input_file=str(source),
        output_file=str(out),
        nup=4,
        draw_borders=True,
    )
    assert result.status == ToolStatus.SUCCESS
    assert media_box(out) == [0, 0, 612, 792]
    texts = page_texts(out)
    assert len(texts) == 2
    assert all(f"Page {n}" in texts[0] for n in (1, 2, 3, 4))
    assert "Page 5" in texts[1]
    with pikepdf.open(out) as pdf:
        assert b" re S" in pdf.pages[0].Contents.read_bytes()


def test_nup_two_up_is_landscape(make_pdf: MakePdf, tmp_path: Path) -> None:
    out = tmp_path / "nup2.pdf"
    result = run("pdf_nup", input_file=str(make_pdf(pages=4)), output_file=str(out))
    assert result.status == ToolStatus.SUCCESS
    assert media_box(out) == [0, 0, 792, 612]
    assert len(page_texts(out)) == 2


def test_nup_vertical_fills_columns_first(make_pdf: MakePdf, tmp_path: Path) -> None:
    source = make_pdf(pages=4)
    horizontal = tmp_path / "h.pdf"
    vertical = tmp_path / "v.pdf"
    run("pdf_nup", input_file=str(source), output_file=str(horizontal), nup=4)
    run(
        "pdf_nup",
        input_file=str(source),
        output_file=str(vertical),
        nup=4,
        ordering="vertical",
    )
    h_second = placements(horizontal)[1]
    v_second = placements(vertical)[1]
    assert h_second[1] > placements(horizontal)[0][1]
    assert h_second[2] == placements(horizontal)[0][2]
    assert v_second[1] == placements(vertical)[0][1]
    assert v_second[2] < placements(vertical)[0][2]


def test_stitch_vertical_matches_paperpilot_dimensions(
    make_pdf: MakePdf, tmp_path: Path
) -> None:
    source = make_pdf(pages=3, size=(300, 400))
    out = tmp_path / "vertical.pdf"
    result = run(
        "pdf_stitch_canvas",
        input_file=str(source),
        output_file=str(out),
        margin_pt=10,
        spacing_pt=5,
    )
    assert result.status == ToolStatus.SUCCESS
    assert media_box(out) == [0, 0, 320, 1230]
    (text,) = page_texts(out)
    assert all(f"Page {n}" in text for n in (1, 2, 3))


def test_stitch_horizontal_matches_paperpilot_dimensions(
    make_pdf: MakePdf, tmp_path: Path
) -> None:
    source = make_pdf(pages=2, size=(200, 500))
    out = tmp_path / "horizontal.pdf"
    result = run(
        "pdf_stitch_canvas",
        input_file=str(source),
        output_file=str(out),
        direction="horizontal",
        margin_pt=20,
        spacing_pt=10,
    )
    assert result.status == ToolStatus.SUCCESS
    assert media_box(out) == [0, 0, 450, 540]


def test_stitch_uses_rotated_page_size(make_pdf: MakePdf, tmp_path: Path) -> None:
    source = make_pdf(pages=1, size=(300, 400))
    rotated = tmp_path / "rotated.pdf"
    with pikepdf.open(source) as pdf:
        pdf.pages[0].obj.Rotate = 90
        pdf.save(rotated)
    out = tmp_path / "out.pdf"
    run("pdf_stitch_canvas", input_file=str(rotated), output_file=str(out))
    assert media_box(out) == [0, 0, 400, 300]


@pytest.mark.parametrize("name", ["pdf_booklet", "pdf_nup", "pdf_stitch_canvas"])
def test_missing_input_is_reported(name: str, tmp_path: Path) -> None:
    result = run(
        name,
        input_file=str(tmp_path / "missing.pdf"),
        output_file=str(tmp_path / "o.pdf"),
    )
    assert result.status == ToolStatus.FAILED
    assert result.errors


@pytest.mark.parametrize(
    ("name", "params"),
    [("pdf_nup", {"nup": 3}), ("pdf_stitch_canvas", {"direction": "diagonal"})],
)
def test_invalid_choice_is_reported(
    name: str, params: dict[str, object], make_pdf: MakePdf, tmp_path: Path
) -> None:
    result = run(
        name,
        input_file=str(make_pdf(pages=1)),
        output_file=str(tmp_path / "o.pdf"),
        **params,
    )
    assert result.status == ToolStatus.FAILED
    assert result.errors


def test_output_may_not_overwrite_input(make_pdf: MakePdf) -> None:
    source = make_pdf(pages=2)
    result = run("pdf_nup", input_file=str(source), output_file=str(source))
    assert result.status == ToolStatus.FAILED
    assert result.errors
