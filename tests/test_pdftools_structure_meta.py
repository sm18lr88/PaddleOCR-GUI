import base64
from collections.abc import Callable
from pathlib import Path

import pikepdf
from reportlab.pdfgen.canvas import Canvas

from paddlepdf.pdftools.runner import run_tool
from paddlepdf.pdftools.structure_meta import TOOLS

type MakePdf = Callable[..., Path]

SPECS = {spec.name: spec for spec in TOOLS}


def test_tool_names() -> None:
    assert sorted(SPECS) == [
        "pdf_attachments",
        "pdf_bookmarks",
        "pdf_classify_type",
        "pdf_info",
        "pdf_metadata",
        "pdf_validate",
    ]


def test_info(make_pdf: MakePdf) -> None:
    result = run_tool(SPECS["pdf_info"], {"input_file": str(make_pdf(pages=4))})
    assert result.status == "success"
    assert isinstance(result.data, dict)
    assert result.data["page_count"] == 4
    assert result.data["encrypted"] is False


def test_metadata_read_then_update(make_pdf: MakePdf, tmp_path: Path) -> None:
    source = make_pdf()
    out = tmp_path / "meta.pdf"
    result = run_tool(
        SPECS["pdf_metadata"],
        {
            "input_file": str(source),
            "output_file": str(out),
            "title": "T1",
            "author": "Ann",
            "keywords": "a, b",
        },
    )
    assert result.status == "success"
    assert result.output_files == (str(out),)
    with pikepdf.open(out) as pdf:
        assert str(pdf.docinfo["/Title"]) == "T1"
        assert str(pdf.docinfo["/Author"]) == "Ann"
        assert str(pdf.docinfo["/Keywords"]) == "a, b"
    read = run_tool(SPECS["pdf_metadata"], {"input_file": str(out)})
    assert isinstance(read.data, dict)
    assert isinstance(read.data["metadata"], dict)
    assert read.data["metadata"]["title"] == "T1"


def test_metadata_updates_existing_xmp(make_pdf: MakePdf, tmp_path: Path) -> None:
    source = make_pdf()
    with pikepdf.open(source, allow_overwriting_input=True) as pdf:
        with pdf.open_metadata() as meta:
            meta["dc:title"] = "Old"
        pdf.save(source)
    out = tmp_path / "xmp.pdf"
    result = run_tool(
        SPECS["pdf_metadata"],
        {"input_file": str(source), "output_file": str(out), "title": "New"},
    )
    assert result.status == "success"
    with pikepdf.open(out) as pdf, pdf.open_metadata() as meta:
        assert meta["dc:title"] == "New"
        assert str(pdf.docinfo["/Title"]) == "New"


def test_metadata_write_without_output_fails(make_pdf: MakePdf) -> None:
    result = run_tool(
        SPECS["pdf_metadata"], {"input_file": str(make_pdf()), "title": "x"}
    )
    assert result.status == "failed"
    assert result.errors


def test_validate_ok_and_empty(make_pdf: MakePdf, tmp_path: Path) -> None:
    ok = run_tool(SPECS["pdf_validate"], {"input_file": str(make_pdf())})
    assert isinstance(ok.data, dict)
    assert ok.data["is_valid"] is True
    assert ok.data["page_count"] == 3
    empty = tmp_path / "empty.pdf"
    pdf = pikepdf.new()
    pdf.save(empty)
    bad = run_tool(SPECS["pdf_validate"], {"input_file": str(empty)})
    assert isinstance(bad.data, dict)
    assert bad.data["is_valid"] is False
    assert "Document has 0 pages" in bad.warnings


def test_validate_missing_file_fails(tmp_path: Path) -> None:
    result = run_tool(SPECS["pdf_validate"], {"input_file": str(tmp_path / "nope.pdf")})
    assert result.status == "failed"
    assert result.errors


def _scan_pdf(path: Path, image_path: Path) -> None:
    from PIL import Image  # noqa: PLC0415

    Image.new("RGB", (200, 300), "gray").save(image_path)
    canvas = Canvas(str(path), pagesize=(200, 300))
    canvas.drawImage(str(image_path), 0, 0, width=200, height=300)
    canvas.showPage()
    canvas.save()


def test_classify_keywords_and_digital(make_pdf: MakePdf) -> None:
    source = make_pdf(
        pages=1, text="Invoice total tax balance due date for services rendered"
    )
    result = run_tool(SPECS["pdf_classify_type"], {"input_file": str(source)})
    assert isinstance(result.data, dict)
    assert result.data["type"] == "Invoice"
    assert result.data["scan_kind"] == "digital"
    assert isinstance(result.data["confidence"], float)
    assert result.data["confidence"] > 0


def test_classify_scanned_and_mixed(make_pdf: MakePdf, tmp_path: Path) -> None:
    scan = tmp_path / "scan.pdf"
    _scan_pdf(scan, tmp_path / "scan.png")
    result = run_tool(SPECS["pdf_classify_type"], {"input_file": str(scan)})
    assert isinstance(result.data, dict)
    assert result.data["scan_kind"] == "scanned"
    assert result.data["type"] == "Unknown"
    mixed = tmp_path / "mixed.pdf"
    with pikepdf.new() as merged:
        for source in (
            make_pdf(pages=1, text="abstract references methodology section"),
            scan,
        ):
            with pikepdf.open(source) as part:
                merged.pages.extend(part.pages)
        merged.save(mixed)
    mixed_result = run_tool(SPECS["pdf_classify_type"], {"input_file": str(mixed)})
    assert isinstance(mixed_result.data, dict)
    assert mixed_result.data["scan_kind"] == "mixed"


def test_attachments_roundtrip(make_pdf: MakePdf, tmp_path: Path) -> None:
    attachments = SPECS["pdf_attachments"]
    added = tmp_path / "added.pdf"
    payload = b"Hello PDF Attachment"
    result = run_tool(
        attachments,
        {
            "input_file": str(make_pdf()),
            "action": "add",
            "output_file": str(added),
            "file_name": "test.txt",
            "description": "Test description",
            "mime_type": "text/plain",
            "file_data_base64": base64.b64encode(payload).decode(),
        },
    )
    assert result.status == "success"
    listed = run_tool(attachments, {"input_file": str(added)})
    assert isinstance(listed.data, dict)
    assert listed.data["total_count"] == 1
    assert listed.data["attachments"] == [
        {
            "name": "test.txt",
            "size_bytes": len(payload),
            "mime_type": "text/plain",
            "description": "Test description",
        }
    ]
    extracted = tmp_path / "out.txt"
    run_tool(
        attachments,
        {
            "input_file": str(added),
            "action": "extract",
            "output_file": str(extracted),
            "file_name": "test.txt",
        },
    )
    assert extracted.read_bytes() == payload
    removed = tmp_path / "removed.pdf"
    run_tool(
        attachments,
        {
            "input_file": str(added),
            "action": "remove",
            "output_file": str(removed),
            "file_name": "test.txt",
        },
    )
    with pikepdf.open(removed) as pdf:
        assert len(pdf.attachments) == 0


def test_attachments_add_from_source_file(make_pdf: MakePdf, tmp_path: Path) -> None:
    data = tmp_path / "data.bin"
    data.write_bytes(b"\x00\x01\x02")
    out = tmp_path / "with.pdf"
    result = run_tool(
        SPECS["pdf_attachments"],
        {
            "input_file": str(make_pdf()),
            "action": "add",
            "output_file": str(out),
            "source_file": str(data),
        },
    )
    assert result.status == "success"
    with pikepdf.open(out) as pdf:
        assert pdf.attachments["data.bin"].get_file().read_bytes() == b"\x00\x01\x02"


def test_attachments_failures(make_pdf: MakePdf, tmp_path: Path) -> None:
    missing = run_tool(
        SPECS["pdf_attachments"],
        {
            "input_file": str(make_pdf()),
            "action": "remove",
            "output_file": str(tmp_path / "o.pdf"),
            "file_name": "nope",
        },
    )
    assert missing.status == "failed"
    assert missing.errors
    bad64 = run_tool(
        SPECS["pdf_attachments"],
        {
            "input_file": str(make_pdf()),
            "action": "add",
            "output_file": str(tmp_path / "o2.pdf"),
            "file_name": "a",
            "file_data_base64": "!!!",
        },
    )
    assert bad64.status == "failed"


def test_bookmarks_set_add_list_clear(make_pdf: MakePdf, tmp_path: Path) -> None:
    bookmarks = SPECS["pdf_bookmarks"]
    source = make_pdf(pages=3)
    first = tmp_path / "b1.pdf"
    result = run_tool(
        bookmarks,
        {
            "input_file": str(source),
            "action": "set",
            "output_file": str(first),
            "bookmarks": [
                {"title": "Ch1", "page": 1, "children": [{"title": "Sec", "page": 2}]}
            ],
        },
    )
    assert result.status == "success"
    second = tmp_path / "b2.pdf"
    run_tool(
        bookmarks,
        {
            "input_file": str(first),
            "action": "add",
            "output_file": str(second),
            "bookmarks": [{"title": "End", "page": 3}],
        },
    )
    listed = run_tool(bookmarks, {"input_file": str(second)})
    assert listed.data == {
        "bookmarks": [
            {
                "title": "Ch1",
                "page": 1,
                "children": [{"title": "Sec", "page": 2, "children": []}],
            },
            {"title": "End", "page": 3, "children": []},
        ]
    }
    with pikepdf.open(second) as pdf, pdf.open_outline() as outline:
        assert [str(item.title) for item in outline.root] == ["Ch1", "End"]
    cleared = tmp_path / "b3.pdf"
    run_tool(
        bookmarks,
        {"input_file": str(second), "action": "clear", "output_file": str(cleared)},
    )
    assert run_tool(bookmarks, {"input_file": str(cleared)}).data == {"bookmarks": []}


def test_bookmarks_page_out_of_range_fails(make_pdf: MakePdf, tmp_path: Path) -> None:
    result = run_tool(
        SPECS["pdf_bookmarks"],
        {
            "input_file": str(make_pdf(pages=1)),
            "action": "add",
            "output_file": str(tmp_path / "x.pdf"),
            "bookmarks": [{"title": "X", "page": 5}],
        },
    )
    assert result.status == "failed"
    assert result.errors
