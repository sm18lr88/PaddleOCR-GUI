import hashlib
import zlib
from collections.abc import Callable
from pathlib import Path

import pikepdf
from PIL import Image

from paddlepdf.pdftools.contract import ToolStatus
from paddlepdf.pdftools.runner import run_tool
from paddlepdf.pdftools.structure_ops import TOOLS

type MakePdf = Callable[..., Path]

SPECS = {spec.name: spec for spec in TOOLS}


def _noise_image(width: int, height: int) -> Image.Image:
    pixels = hashlib.shake_256(b"noise").digest(width * height * 3)
    return Image.frombytes("RGB", (width, height), pixels)


def _image_pdf(path: Path, image: Image.Image) -> Path:
    pdf = pikepdf.new()
    stream = pdf.make_stream(
        zlib.compress(image.tobytes()),
        Type=pikepdf.Name.XObject,
        Subtype=pikepdf.Name.Image,
        Width=image.width,
        Height=image.height,
        ColorSpace=pikepdf.Name.DeviceRGB,
        BitsPerComponent=8,
        Filter=pikepdf.Name.FlateDecode,
    )
    page = pdf.add_blank_page(page_size=(612, 792))
    page.obj.Resources = pikepdf.Dictionary(XObject=pikepdf.Dictionary(Im0=stream))
    page.obj.Contents = pdf.make_stream(b"q 400 0 0 400 100 200 cm /Im0 Do Q")
    pdf.save(path)
    return path


def test_compress_recompresses_and_downscales_images(tmp_path: Path) -> None:
    source = _image_pdf(tmp_path / "photo.pdf", _noise_image(1200, 900))
    target = tmp_path / "small.pdf"

    result = run_tool(
        SPECS["pdf_compress"],
        {"input_file": str(source), "output_file": str(target), "quality": "low"},
    )

    assert result.status == ToolStatus.SUCCESS, result.errors
    assert isinstance(result.data, dict)
    assert result.data["images_recompressed"] == 1
    assert result.data["kept_original"] is False
    assert result.data["output_size"] == target.stat().st_size
    assert target.stat().st_size < source.stat().st_size
    with pikepdf.open(target) as pdf:
        image = pdf.pages[0].get_images()["/Im0"]
        assert image.Filter == pikepdf.Name.DCTDecode
        assert (int(image.Width), int(image.Height)) == (1024, 768)


def test_compress_never_grows_the_file(make_pdf: MakePdf, tmp_path: Path) -> None:
    source = make_pdf(pages=1)
    target = tmp_path / "same.pdf"

    result = run_tool(
        SPECS["pdf_compress"],
        {"input_file": str(source), "output_file": str(target), "quality": "90"},
    )

    assert result.status == ToolStatus.SUCCESS, result.errors
    assert isinstance(result.data, dict)
    assert result.data["jpeg_quality"] == 90
    assert target.stat().st_size <= source.stat().st_size
    with pikepdf.open(target) as pdf:
        assert len(pdf.pages) == 1


def test_compress_rejects_unknown_quality(make_pdf: MakePdf, tmp_path: Path) -> None:
    result = run_tool(
        SPECS["pdf_compress"],
        {
            "input_file": str(make_pdf()),
            "output_file": str(tmp_path / "out.pdf"),
            "quality": "ultra",
        },
    )

    assert result.status == ToolStatus.FAILED
    assert "quality" in result.errors[0]


def test_extract_images_writes_decodable_files(tmp_path: Path) -> None:
    source = _image_pdf(tmp_path / "photo.pdf", _noise_image(64, 48))
    out_dir = tmp_path / "images"

    result = run_tool(
        SPECS["pdf_extract_images"],
        {"input_file": str(source), "output_dir": str(out_dir)},
    )

    assert result.status == ToolStatus.SUCCESS, result.errors
    assert len(result.output_files) == 1
    written = Path(result.output_files[0])
    assert written.parent == out_dir
    with Image.open(written) as image:
        assert image.size == (64, 48)
    assert isinstance(result.data, dict)
    assert result.data["image_count"] == 1


def test_extract_images_warns_when_none_found(
    make_pdf: MakePdf, tmp_path: Path
) -> None:
    result = run_tool(
        SPECS["pdf_extract_images"],
        {"input_file": str(make_pdf()), "output_dir": str(tmp_path / "none")},
    )

    assert result.status == ToolStatus.SUCCESS
    assert result.output_files == ()
    assert result.warnings


def test_render_selected_pages_to_jpeg(make_pdf: MakePdf, tmp_path: Path) -> None:
    source = make_pdf(pages=3)

    result = run_tool(
        SPECS["pdf_render"],
        {
            "input_file": str(source),
            "output_dir": str(tmp_path / "renders"),
            "pages": "1,last",
            "dpi": 72,
            "image_format": "jpeg",
        },
    )

    assert result.status == ToolStatus.SUCCESS, result.errors
    names = [Path(file).name for file in result.output_files]
    assert names == ["sample_page1.jpg", "sample_page3.jpg"]
    for file in result.output_files:
        with Image.open(file) as image:
            assert image.format == "JPEG"
            assert image.size == (612, 792)


def test_render_rejects_out_of_range_page(make_pdf: MakePdf, tmp_path: Path) -> None:
    result = run_tool(
        SPECS["pdf_render"],
        {"input_file": str(make_pdf()), "output_dir": str(tmp_path), "pages": "9"},
    )

    assert result.status == ToolStatus.FAILED
    assert result.errors


def test_compare_reports_text_and_visual_differences(
    make_pdf: MakePdf, tmp_path: Path
) -> None:
    first = make_pdf("a.pdf", pages=2, text="alpha clause")
    second = make_pdf("b.pdf", pages=3, text="beta clause")
    report = tmp_path / "diff.json"

    result = run_tool(
        SPECS["pdf_compare"],
        {
            "input_file_a": str(first),
            "input_file_b": str(second),
            "output_file": str(report),
            "output_dir": str(tmp_path / "visual"),
            "visual_diff": True,
        },
    )

    assert result.status == ToolStatus.SUCCESS, result.errors
    assert isinstance(result.data, dict)
    assert result.data["diff_detected"] is True
    assert result.data["changed_pages"] == [1, 2, 3]
    text_diffs = result.data["text_differences"]
    assert isinstance(text_diffs, list)
    statuses = [entry["status"] for entry in text_diffs if isinstance(entry, dict)]
    assert statuses == ["changed", "changed", "added"]
    assert report.read_text(encoding="utf-8").startswith("{")
    diff_images = [Path(file) for file in result.output_files if file.endswith(".png")]
    assert [image.name for image in diff_images] == [
        "a_diff_page1.png",
        "a_diff_page2.png",
    ]
    with Image.open(diff_images[0]) as image:
        assert image.size == (612, 792)


def test_compare_identical_files_find_no_difference(
    make_pdf: MakePdf, tmp_path: Path
) -> None:
    first = make_pdf("same.pdf", pages=2)
    copy = tmp_path / "copy.pdf"
    copy.write_bytes(first.read_bytes())

    result = run_tool(
        SPECS["pdf_compare"],
        {"input_file_a": str(first), "input_file_b": str(copy)},
    )

    assert result.status == ToolStatus.SUCCESS
    assert isinstance(result.data, dict)
    assert result.data["diff_detected"] is False
    assert result.data["changed_pages"] == []


def test_compare_visual_needs_output_dir(make_pdf: MakePdf) -> None:
    first = make_pdf("x.pdf")
    second = make_pdf("y.pdf")

    result = run_tool(
        SPECS["pdf_compare"],
        {"input_file_a": str(first), "input_file_b": str(second), "visual_diff": True},
    )

    assert result.status == ToolStatus.FAILED
    assert "output_dir" in result.errors[0]
