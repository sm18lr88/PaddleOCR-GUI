import json
from collections.abc import Callable
from pathlib import Path

import pikepdf
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen.canvas import Canvas

from paddlepdf.pdftools.contract import ToolSpec
from paddlepdf.pdftools.pdfium import find_text_boxes, page_texts, render_page
from paddlepdf.pdftools.runner import run_tool
from paddlepdf.pdftools.security import TOOLS

type MakePdf = Callable[..., Path]

SPECS: dict[str, ToolSpec] = {spec.name: spec for spec in TOOLS}
HIDDEN = "ALPHA-42"
BLACK = (0, 0, 0)


def _pixel(path: Path, page_index: int, x: float, y: float) -> tuple[int, ...]:
    image = render_page(path, page_index, dpi=72).convert("RGB")
    value = image.getpixel((round(x), round(image.height - y)))
    assert isinstance(value, tuple)
    return value


def test_redact_search_removes_text_and_draws_box(
    make_pdf: MakePdf, tmp_path: Path
) -> None:
    source = make_pdf(text=f"Secret code {HIDDEN} here")
    left, bottom, right, top = find_text_boxes(source, HIDDEN)[0][0]
    out = tmp_path / "redacted.pdf"
    result = run_tool(
        SPECS["pdf_redact"],
        {
            "input_file": str(source),
            "output_file": str(out),
            "search_text": HIDDEN,
            "pages": "1-2",
        },
    )
    assert result.status == "success", result.errors
    assert isinstance(result.data, dict)
    assert result.data["rasterized_pages"] == [1, 2]
    texts = page_texts(out)
    assert HIDDEN not in texts[0]
    assert HIDDEN not in texts[1]
    assert HIDDEN in texts[2]
    assert "Page 3" in texts[2]
    assert _pixel(out, 0, (left + right) / 2, (bottom + top) / 2) == BLACK
    assert _pixel(out, 0, 30, 30) == (255, 255, 255)
    assert HIDDEN.encode() not in out.read_bytes()


def test_redact_explicit_region(make_pdf: MakePdf, tmp_path: Path) -> None:
    source = make_pdf(pages=2)
    out = tmp_path / "region.pdf"
    region = {"page": 2, "x": 60, "y": 700, "width": 200, "height": 40}
    result = run_tool(
        SPECS["pdf_redact"],
        {"input_file": str(source), "output_file": str(out), "regions": [region]},
    )
    assert result.status == "success", result.errors
    assert isinstance(result.data, dict)
    assert result.data["redaction_count"] == 1
    texts = page_texts(out)
    assert "Page 1" in texts[0]
    assert "Page 2" not in texts[1]
    assert _pixel(out, 1, 160, 720) == BLACK
    with pikepdf.open(out) as pdf:
        assert len(pdf.pages) == 2


def test_redact_without_targets_fails(make_pdf: MakePdf, tmp_path: Path) -> None:
    result = run_tool(
        SPECS["pdf_redact"],
        {"input_file": str(make_pdf()), "output_file": str(tmp_path / "x.pdf")},
    )
    assert result.status == "failed"
    assert result.errors


def _active_pdf(source: Path, target: Path) -> None:
    note = target.with_name("note.txt")
    note.write_bytes(b"hidden")
    with pikepdf.open(source) as pdf:
        pdf.docinfo["/Title"] = "Confidential"
        script = pikepdf.Dictionary(
            S=pikepdf.Name.JavaScript, JS=pikepdf.String("app.alert(1)")
        )
        pdf.Root.OpenAction = pdf.make_indirect(script)
        pdf.Root.Names = pikepdf.Dictionary(
            JavaScript=pikepdf.Dictionary(Names=pikepdf.Array())
        )
        pdf.attachments["note.txt"] = pikepdf.AttachedFileSpec.from_filepath(pdf, note)
        page = pdf.pages[0].obj
        page.AA = pikepdf.Dictionary(O=script)
        page.Thumb = pdf.make_stream(b"thumb")
        page.PieceInfo = pikepdf.Dictionary()
        link = pikepdf.Dictionary(
            Type=pikepdf.Name.Annot,
            Subtype=pikepdf.Name.Link,
            Rect=pikepdf.Array([0, 0, 10, 10]),
            A=pikepdf.Dictionary(
                S=pikepdf.Name.URI, URI=pikepdf.String("http://example.com")
            ),
        )
        page.Annots = pikepdf.Array([pdf.make_indirect(link)])
        pdf.save(target)


def test_sanitize_strips_active_content(make_pdf: MakePdf, tmp_path: Path) -> None:
    source = tmp_path / "active.pdf"
    _active_pdf(make_pdf(), source)
    out = tmp_path / "clean.pdf"
    result = run_tool(
        SPECS["pdf_sanitize"], {"input_file": str(source), "output_file": str(out)}
    )
    assert result.status == "success", result.errors
    assert isinstance(result.data, dict)
    assert result.data["metadata_stripped"] is True
    assert result.data["scripts_removed"] == 3
    assert result.data["external_actions_removed"] == 1
    assert result.data["attachments_removed"] == 2
    assert result.data["thumbnails_removed"] == 1
    assert result.data["private_data_removed"] == 1
    with pikepdf.open(out) as pdf:
        assert "/Info" not in pdf.trailer
        assert "/OpenAction" not in pdf.Root
        assert "/AF" not in pdf.Root
        assert len(pdf.attachments) == 0
        page = pdf.pages[0].obj
        for key in ("/AA", "/Thumb", "/PieceInfo"):
            assert key not in page
        annots = page.Annots
        assert isinstance(annots, pikepdf.Array)
        link = annots[0]
        assert isinstance(link, pikepdf.Dictionary)
        assert "/A" not in link
    assert b"app.alert" not in out.read_bytes()
    assert "Page 1" in page_texts(out)[0]


def test_sanitize_respects_flags(make_pdf: MakePdf, tmp_path: Path) -> None:
    source = tmp_path / "active.pdf"
    _active_pdf(make_pdf(), source)
    out = tmp_path / "partial.pdf"
    result = run_tool(
        SPECS["pdf_sanitize"],
        {
            "input_file": str(source),
            "output_file": str(out),
            "remove_metadata": False,
            "remove_attachments": False,
        },
    )
    assert result.status == "success", result.errors
    with pikepdf.open(out) as pdf:
        assert str(pdf.docinfo["/Title"]) == "Confidential"
        assert len(pdf.attachments) == 1
        assert "/OpenAction" not in pdf.Root


def _pii_pdf(path: Path) -> Path:
    canvas = Canvas(str(path), pagesize=letter)
    lines = [
        "SSN: 123-45-6789",
        "Card: 4111 1111 1111 1111",
        "Mail: john.doe@example.com",
        "Call (555) 123-4567 today",
        "Account DE89370400440532013000",
    ]
    for offset, line in enumerate(lines):
        canvas.drawString(72, 700 - offset * 30, line)
    canvas.showPage()
    canvas.drawString(72, 700, "Nothing personal")
    canvas.showPage()
    canvas.save()
    return path


def test_pii_scan_finds_masked_values(tmp_path: Path) -> None:
    source = _pii_pdf(tmp_path / "pii.pdf")
    report_file = tmp_path / "report.json"
    result = run_tool(
        SPECS["document_pii_scan"],
        {"input_file": str(source), "output_file": str(report_file)},
    )
    assert result.status == "success", result.errors
    assert result.output_files == (str(report_file),)
    assert isinstance(result.data, dict)
    findings = result.data["findings"]
    assert isinstance(findings, list)
    found = {
        (item["category"], item["value_masked"])
        for item in findings
        if isinstance(item, dict)
    }
    assert ("ssn", "XXX-XX-6789") in found
    assert ("credit_card", "**** **** **** 1111") in found
    assert ("email", "j***e@example.com") in found
    assert ("phone", "(***) ***-4567") in found
    assert ("iban", "DE** **** **** **** **3000") in found
    assert all(isinstance(item, dict) and item["page"] == 1 for item in findings)
    assert result.data["total_findings"] == len(findings)
    assert json.loads(report_file.read_text(encoding="utf-8")) == result.data


def test_pii_scan_category_toggle(tmp_path: Path) -> None:
    source = _pii_pdf(tmp_path / "pii.pdf")
    result = run_tool(
        SPECS["document_pii_scan"],
        {"input_file": str(source), "scan_emails": False, "scan_ssn": False},
    )
    assert result.status == "success", result.errors
    assert result.output_files == ()
    assert isinstance(result.data, dict)
    categories = result.data["findings_by_category"]
    assert isinstance(categories, dict)
    assert "email" not in categories
    assert "ssn" not in categories
    assert categories.get("credit_card") == 1
