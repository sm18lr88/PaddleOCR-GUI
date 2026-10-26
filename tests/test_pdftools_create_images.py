import zipfile
from collections.abc import Callable
from io import BytesIO
from pathlib import Path

import pikepdf
from PIL import Image

from paddlepdf.pdftools.contract import ToolSpec, ToolStatus
from paddlepdf.pdftools.create import TOOLS
from paddlepdf.pdftools.runner import run_tool

type MakePdf = Callable[..., Path]

SPECS = {spec.name: spec for spec in TOOLS}


def _spec(name: str) -> ToolSpec:
    return SPECS[name]


def _image_bytes(size: tuple[int, int], fmt: str, mode: str = "RGB") -> bytes:
    buffer = BytesIO()
    Image.new(mode, size, "orange").save(buffer, fmt)
    return buffer.getvalue()


def _page_boxes(path: Path) -> list[tuple[int, int]]:
    with pikepdf.open(path) as pdf:
        return [
            (round(float(page.mediabox[2])), round(float(page.mediabox[3])))
            for page in pdf.pages
        ]


def _image_filters(path: Path) -> list[str]:
    with pikepdf.open(path) as pdf:
        return [
            str(image.get("/Filter"))
            for page in pdf.pages
            for image in page.get_images().values()
        ]


def test_images_to_pdf_sizes_pages_to_images_in_order(tmp_path: Path) -> None:
    png = tmp_path / "wide.png"
    png.write_bytes(_image_bytes((100, 50), "PNG", "RGBA"))
    jpeg = tmp_path / "tall.jpg"
    jpeg.write_bytes(_image_bytes((40, 80), "JPEG"))
    target = tmp_path / "album.pdf"

    result = run_tool(
        _spec("pdf_images_to_pdf"),
        {"input_files": [str(png), str(jpeg)], "output_file": str(target)},
    )

    assert result.status is ToolStatus.SUCCESS, result.errors
    assert result.output_files == (str(target),)
    assert _page_boxes(target) == [(100, 50), (40, 80)]
    assert any("/DCTDecode" in name for name in _image_filters(target))


def test_images_to_pdf_fits_onto_paper_with_auto_orientation(tmp_path: Path) -> None:
    wide = tmp_path / "wide.webp"
    wide.write_bytes(_image_bytes((300, 100), "WEBP"))
    tall = tmp_path / "tall.bmp"
    tall.write_bytes(_image_bytes((100, 300), "BMP"))
    target = tmp_path / "paper.pdf"

    result = run_tool(
        _spec("pdf_images_to_pdf"),
        {
            "input_files": [str(wide), str(tall)],
            "output_file": str(target),
            "page_size": "A4",
            "margin_mm": 10,
        },
    )

    assert result.status is ToolStatus.SUCCESS, result.errors
    assert _page_boxes(target) == [(842, 595), (595, 842)]


def test_images_to_pdf_fails_for_missing_or_corrupt_images(tmp_path: Path) -> None:
    broken = tmp_path / "broken.png"
    broken.write_bytes(b"not an image")
    for inputs in ([str(tmp_path / "missing.png")], [str(broken)], []):
        result = run_tool(
            _spec("pdf_images_to_pdf"),
            {"input_files": inputs, "output_file": str(tmp_path / "out.pdf")},
        )
        assert result.status is ToolStatus.FAILED
        assert result.errors


def test_comic_archive_pdf_to_cbz_renders_selected_pages(
    make_pdf: MakePdf, tmp_path: Path
) -> None:
    source = make_pdf(pages=3)
    target = tmp_path / "comic.cbz"

    result = run_tool(
        _spec("pdf_comic_archive"),
        {
            "input_file": str(source),
            "output_file": str(target),
            "pages": "1,3",
            "dpi": 72,
        },
    )

    assert result.status is ToolStatus.SUCCESS, result.errors
    with zipfile.ZipFile(target) as archive:
        names = archive.namelist()
        assert names == ["page-001.jpg", "page-002.jpg"]
        with Image.open(BytesIO(archive.read(names[0]))) as page:
            assert page.format == "JPEG"
            assert page.size == (612, 792)


def test_comic_archive_cbz_to_pdf_uses_natural_order(tmp_path: Path) -> None:
    source = tmp_path / "issue.cbz"
    with zipfile.ZipFile(source, "w") as archive:
        archive.writestr("p10.png", _image_bytes((30, 30), "PNG"))
        archive.writestr("p2.png", _image_bytes((20, 20), "PNG"))
        archive.writestr("p1.jpg", _image_bytes((10, 10), "JPEG"))
        archive.writestr("__MACOSX/._p1.jpg", b"resource fork")
        archive.writestr("ComicInfo.xml", "<ComicInfo/>")
    target = tmp_path / "issue.pdf"

    result = run_tool(
        _spec("pdf_comic_archive"),
        {"input_file": str(source), "output_file": str(target)},
    )

    assert result.status is ToolStatus.SUCCESS, result.errors
    assert _page_boxes(target) == [(10, 10), (20, 20), (30, 30)]
    assert isinstance(result.data, dict)
    assert result.data["pages"] == ["p1.jpg", "p2.png", "p10.png"]


def test_comic_archive_rejects_cbr_and_wrong_direction(
    make_pdf: MakePdf, tmp_path: Path
) -> None:
    cbr = tmp_path / "issue.cbr"
    cbr.write_bytes(b"Rar!\x1a\x07\x00")
    rar_result = run_tool(
        _spec("pdf_comic_archive"),
        {"input_file": str(cbr), "output_file": str(tmp_path / "issue.pdf")},
    )
    wrong_result = run_tool(
        _spec("pdf_comic_archive"),
        {"input_file": str(make_pdf()), "output_file": str(tmp_path / "issue.cbr")},
    )

    assert rar_result.status is ToolStatus.FAILED
    assert "CBR" in rar_result.errors[0]
    assert wrong_result.status is ToolStatus.FAILED
    assert ".cbz" in wrong_result.errors[0]
