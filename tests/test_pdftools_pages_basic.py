from collections.abc import Callable
from pathlib import Path

import pikepdf

from paddlepdf.pdftools.common import open_pdf
from paddlepdf.pdftools.contract import ToolResult, ToolSpec, ToolStatus
from paddlepdf.pdftools.pages_basic import TOOLS
from paddlepdf.pdftools.pdfium import page_texts
from paddlepdf.pdftools.runner import run_tool

type MakePdf = Callable[..., Path]


def spec(name: str) -> ToolSpec:
    return next(s for s in TOOLS if s.name == name)


def run(name: str, **params: object) -> ToolResult:
    result = run_tool(spec(name), params)
    assert result.status == ToolStatus.SUCCESS, result.errors
    return result


def labels(path: str | Path) -> list[str]:
    return [text.strip() for text in page_texts(Path(path), None)]


def failed(name: str, **params: object) -> ToolResult:
    result = run_tool(spec(name), params)
    assert result.status == ToolStatus.FAILED
    assert result.errors
    return result


def test_tool_names() -> None:
    assert sorted(s.name for s in TOOLS) == [
        "pdf_burst",
        "pdf_delete_pages",
        "pdf_extract_pages",
        "pdf_merge",
        "pdf_reorder_pages",
        "pdf_rotate",
        "pdf_split",
    ]


def test_merge_preserves_order(make_pdf: MakePdf, tmp_path: Path) -> None:
    first = make_pdf("a.pdf", pages=2, text="A")
    second = make_pdf("b.pdf", pages=1, text="B")
    out = tmp_path / "m.pdf"
    result = run(
        "pdf_merge", input_files=[str(second), str(first)], output_file=str(out)
    )
    assert result.output_files == (str(out),)
    texts = labels(out)
    assert len(texts) == 3
    assert "B" in texts[0]
    assert "Page 1" in texts[1]
    assert "A" in texts[2]


def test_merge_needs_two_inputs(make_pdf: MakePdf, tmp_path: Path) -> None:
    only = make_pdf("a.pdf")
    failed("pdf_merge", input_files=[str(only)], output_file=str(tmp_path / "m.pdf"))


def test_split_every(make_pdf: MakePdf, tmp_path: Path) -> None:
    src = make_pdf("doc.pdf", pages=5)
    out = tmp_path / "parts"
    result = run("pdf_split", input_file=str(src), output_dir=str(out), every=2)
    assert [Path(f).name for f in result.output_files] == [
        "doc-1.pdf",
        "doc-2.pdf",
        "doc-3.pdf",
    ]
    assert [len(open_pdf(Path(f)).pages) for f in result.output_files] == [2, 2, 1]
    assert "Page 5" in labels(result.output_files[2])[0]


def test_split_after_points_and_default(make_pdf: MakePdf, tmp_path: Path) -> None:
    src = make_pdf("doc.pdf", pages=4)
    cut = run(
        "pdf_split",
        input_file=str(src),
        output_dir=str(tmp_path / "c"),
        split_after="1-3",
    )
    assert [len(open_pdf(Path(f)).pages) for f in cut.output_files] == [3, 1]
    every_page = run("pdf_split", input_file=str(src), output_dir=str(tmp_path / "e"))
    assert len(every_page.output_files) == 4


def test_split_bad_cut_fails(make_pdf: MakePdf, tmp_path: Path) -> None:
    src = make_pdf("doc.pdf", pages=3)
    failed(
        "pdf_split",
        input_file=str(src),
        output_dir=str(tmp_path / "o"),
        split_after="9",
    )


def test_burst(make_pdf: MakePdf, tmp_path: Path) -> None:
    src = make_pdf("doc.pdf", pages=3)
    result = run("pdf_burst", input_file=str(src), output_dir=str(tmp_path / "b"))
    assert [Path(f).name for f in result.output_files] == [
        "doc-1.pdf",
        "doc-2.pdf",
        "doc-3.pdf",
    ]
    assert [len(open_pdf(Path(f)).pages) for f in result.output_files] == [1, 1, 1]
    assert "Page 2" in labels(result.output_files[1])[0]


def test_extract_pages(make_pdf: MakePdf, tmp_path: Path) -> None:
    src = make_pdf("doc.pdf", pages=5)
    out = tmp_path / "x.pdf"
    run("pdf_extract_pages", input_file=str(src), pages="4,2", output_file=str(out))
    texts = labels(out)
    assert len(texts) == 2
    assert "Page 2" in texts[0]
    assert "Page 4" in texts[1]


def test_delete_pages(make_pdf: MakePdf, tmp_path: Path) -> None:
    src = make_pdf("doc.pdf", pages=4)
    out = tmp_path / "d.pdf"
    run("pdf_delete_pages", input_file=str(src), pages="2,last", output_file=str(out))
    texts = labels(out)
    assert len(texts) == 2
    assert "Page 1" in texts[0]
    assert "Page 3" in texts[1]


def test_delete_all_pages_fails(make_pdf: MakePdf, tmp_path: Path) -> None:
    src = make_pdf("doc.pdf", pages=2)
    failed(
        "pdf_delete_pages",
        input_file=str(src),
        pages="all",
        output_file=str(tmp_path / "d.pdf"),
    )


def test_reorder_pages(make_pdf: MakePdf, tmp_path: Path) -> None:
    src = make_pdf("doc.pdf", pages=3)
    out = tmp_path / "r.pdf"
    run("pdf_reorder_pages", input_file=str(src), order="3,1,2", output_file=str(out))
    assert [t.split()[-1] for t in labels(out)] == ["3", "1", "2"]


def test_reorder_invalid_fails(make_pdf: MakePdf, tmp_path: Path) -> None:
    src = make_pdf("doc.pdf", pages=3)
    out = str(tmp_path / "r.pdf")
    failed("pdf_reorder_pages", input_file=str(src), order="3,1", output_file=out)
    failed("pdf_reorder_pages", input_file=str(src), order="3,1,1", output_file=out)


def test_rotate_combines_with_existing(make_pdf: MakePdf, tmp_path: Path) -> None:
    src = make_pdf("doc.pdf", pages=2)
    with pikepdf.open(src, allow_overwriting_input=True) as pdf:
        pdf.pages[1].obj["/Rotate"] = 90
        pdf.save(src)
    out = tmp_path / "rot.pdf"
    run("pdf_rotate", input_file=str(src), angle=270, pages="2", output_file=str(out))
    with pikepdf.open(out) as pdf:
        assert int(pdf.pages[0].obj.get("/Rotate", 0)) == 0
        assert int(pdf.pages[1].obj["/Rotate"]) == 0
    all_out = tmp_path / "all.pdf"
    run("pdf_rotate", input_file=str(src), angle=90, output_file=str(all_out))
    with pikepdf.open(all_out) as pdf:
        assert [int(p.obj["/Rotate"]) for p in pdf.pages] == [90, 180]


def test_rotate_invalid_angle_fails(make_pdf: MakePdf, tmp_path: Path) -> None:
    src = make_pdf("doc.pdf")
    failed(
        "pdf_rotate", input_file=str(src), angle=45, output_file=str(tmp_path / "o.pdf")
    )


def test_missing_input_fails(tmp_path: Path) -> None:
    failed(
        "pdf_burst",
        input_file=str(tmp_path / "none.pdf"),
        output_dir=str(tmp_path / "o"),
    )
