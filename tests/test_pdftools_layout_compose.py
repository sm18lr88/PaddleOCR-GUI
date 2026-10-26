import base64
from collections.abc import Callable
from pathlib import Path

import pikepdf
import pytest

from paddlepdf.pdftools.contract import ToolResult, ToolSpec, ToolStatus
from paddlepdf.pdftools.layout import TOOLS
from paddlepdf.pdftools.pdfium import page_texts, render_page
from paddlepdf.pdftools.runner import run_tool

type MakePdf = Callable[..., Path]

SPECS: dict[str, ToolSpec] = {spec.name: spec for spec in TOOLS}


def run(name: str, **params: object) -> ToolResult:
    return run_tool(SPECS[name], params)


def has_template(path: Path, index: int) -> bool:
    with pikepdf.open(path) as pdf:
        xobjects = pdf.pages[index].resources.get("/XObject")
        return xobjects is not None and "/TplOverlay" in xobjects


def page_content(path: Path, index: int = 0) -> bytes:
    with pikepdf.open(path) as pdf:
        page = pdf.pages[index]
        page.contents_coalesce()
        return page.Contents.read_bytes()


def pixels(path: Path, index: int = 0) -> bytes:
    return render_page(path, index, dpi=36).convert("RGB").tobytes()


def corner(path: Path, index: int = 0) -> tuple[int, ...]:
    return tuple(pixels(path, index)[:3])


def test_tool_names_match_paperpilot() -> None:
    assert sorted(SPECS) == [
        "pdf_booklet",
        "pdf_invert_colors",
        "pdf_nup",
        "pdf_overlay_underlay",
        "pdf_stitch_canvas",
    ]


def test_underlay_draws_template_before_page_content(
    make_pdf: MakePdf, tmp_path: Path
) -> None:
    source = make_pdf(pages=2)
    template = make_pdf("tpl.pdf", pages=1, text="LETTERHEAD")
    out = tmp_path / "under.pdf"
    result = run(
        "pdf_overlay_underlay",
        input_file=str(source),
        output_file=str(out),
        template_file=str(template),
    )
    assert result.status == ToolStatus.SUCCESS
    assert result.data == {"mode": "underlay", "stamped_pages": [1, 2]}
    assert all("LETTERHEAD" in text and "Page" in text for text in page_texts(out))
    content = page_content(out)
    assert content.index(b"TplOverlay") < content.index(b"BT")


def test_overlay_with_opacity_on_selected_pages(
    make_pdf: MakePdf, tmp_path: Path
) -> None:
    source = make_pdf(pages=3)
    template = make_pdf("tpl.pdf", pages=1, text="STAMP")
    out = tmp_path / "over.pdf"
    result = run(
        "pdf_overlay_underlay",
        input_file=str(source),
        output_file=str(out),
        template_file=str(template),
        mode="overlay",
        pages="2,last",
        opacity=0.4,
    )
    assert result.status == ToolStatus.SUCCESS
    assert [has_template(out, i) for i in range(3)] == [False, True, True]
    content = page_content(out, 1)
    assert content.index(b"BT") < content.index(b"TplOverlay")
    assert b"/TplOpacity gs" in content
    with pikepdf.open(out) as pdf:
        state = pdf.pages[1].resources["/ExtGState"]["/TplOpacity"]
        assert float(state["/ca"]) == pytest.approx(0.4)
    assert "STAMP" in page_texts(out)[1]
    assert "STAMP" not in page_texts(out)[0]


def test_overlay_accepts_base64_template(make_pdf: MakePdf, tmp_path: Path) -> None:
    template = make_pdf("tpl.pdf", pages=1, text="INLINE")
    out = tmp_path / "inline.pdf"
    result = run(
        "pdf_overlay_underlay",
        input_file=str(make_pdf(pages=1)),
        output_file=str(out),
        template_data=base64.b64encode(template.read_bytes()).decode(),
        pages="first",
    )
    assert result.status == ToolStatus.SUCCESS
    assert "INLINE" in page_texts(out)[0]


@pytest.mark.parametrize(
    "template",
    [{}, {"template_data": "not base64!"}, {"template_file": "missing-template.pdf"}],
)
def test_overlay_failures_are_reported(
    template: dict[str, str], make_pdf: MakePdf, tmp_path: Path
) -> None:
    result = run(
        "pdf_overlay_underlay",
        input_file=str(make_pdf(pages=1)),
        output_file=str(tmp_path / "o.pdf"),
        **template,
    )
    assert result.status == ToolStatus.FAILED
    assert result.errors


def test_true_invert_flips_page_and_keeps_text(
    make_pdf: MakePdf, tmp_path: Path
) -> None:
    out = tmp_path / "inverted.pdf"
    result = run(
        "pdf_invert_colors",
        input_file=str(make_pdf(pages=1)),
        output_file=str(out),
        mode="true_invert",
    )
    assert result.status == ToolStatus.SUCCESS
    assert corner(out) == (0, 0, 0)
    assert max(pixels(out)) >= 150
    assert "Page 1" in page_texts(out)[0]


def test_dark_mode_is_the_default_soft_dark(make_pdf: MakePdf, tmp_path: Path) -> None:
    out = tmp_path / "dark.pdf"
    run("pdf_invert_colors", input_file=str(make_pdf(pages=1)), output_file=str(out))
    red, green, blue = corner(out)
    assert 40 <= red <= 62
    assert abs(red - green) <= 2
    assert abs(red - blue) <= 2


def test_sepia_tints_paper_and_high_contrast_is_black_white(
    make_pdf: MakePdf, tmp_path: Path
) -> None:
    source = make_pdf(pages=1)
    sepia = tmp_path / "sepia.pdf"
    contrast = tmp_path / "contrast.pdf"
    run(
        "pdf_invert_colors",
        input_file=str(source),
        output_file=str(sepia),
        mode="sepia",
    )
    run(
        "pdf_invert_colors",
        input_file=str(source),
        output_file=str(contrast),
        mode="high_contrast",
    )
    red, green, blue = corner(sepia)
    assert red > green > blue
    assert red >= 240
    assert corner(contrast) == (0, 0, 0)
    assert max(pixels(contrast)) == 255


def test_invert_only_selected_pages(make_pdf: MakePdf, tmp_path: Path) -> None:
    out = tmp_path / "subset.pdf"
    result = run(
        "pdf_invert_colors",
        input_file=str(make_pdf(pages=3)),
        output_file=str(out),
        mode="true_invert",
        pages="2",
    )
    assert result.data == {"mode": "true_invert", "recolored_pages": [2]}
    assert corner(out, 0) == (255, 255, 255)
    assert corner(out, 1) == (0, 0, 0)
    assert corner(out, 2) == (255, 255, 255)


@pytest.mark.parametrize("params", [{"mode": "neon"}, {"pages": "9"}])
def test_invert_failures_are_reported(
    params: dict[str, str], make_pdf: MakePdf, tmp_path: Path
) -> None:
    result = run(
        "pdf_invert_colors",
        input_file=str(make_pdf(pages=1)),
        output_file=str(tmp_path / "o.pdf"),
        **params,
    )
    assert result.status == ToolStatus.FAILED
    assert result.errors
