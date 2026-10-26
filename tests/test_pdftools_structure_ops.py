from collections.abc import Callable
from pathlib import Path

import pikepdf
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen.canvas import Canvas

from paddlepdf.pdftools.contract import ToolStatus
from paddlepdf.pdftools.pdfium import page_texts
from paddlepdf.pdftools.runner import run_tool
from paddlepdf.pdftools.structure_ops import TOOLS

type MakePdf = Callable[..., Path]

SPECS = {spec.name: spec for spec in TOOLS}


def test_lane_registers_every_paperpilot_tool() -> None:
    assert sorted(SPECS) == [
        "pdf_compare",
        "pdf_compress",
        "pdf_extract_images",
        "pdf_flatten",
        "pdf_linearize",
        "pdf_render",
        "pdf_repair",
        "pdf_to_pdf_a",
    ]


def test_repair_rebuilds_broken_xref(make_pdf: MakePdf, tmp_path: Path) -> None:
    source = make_pdf(pages=3)
    content = source.read_bytes()
    marker = content.rindex(b"startxref")
    broken = tmp_path / "broken.pdf"
    broken.write_bytes(content[:marker] + b"startxref\n999999\n%%EOF\n")
    target = tmp_path / "repaired.pdf"

    result = run_tool(
        SPECS["pdf_repair"], {"input_file": str(broken), "output_file": str(target)}
    )

    assert result.status == ToolStatus.SUCCESS, result.errors
    assert isinstance(result.data, dict)
    assert result.data["problems_found"]
    assert result.data["problems_after_repair"] == []
    assert result.data["repaired"] is True
    texts = page_texts(target)
    assert [text.strip() for text in texts] == ["Page 1", "Page 2", "Page 3"]


def test_repair_fails_on_unrecoverable_file(tmp_path: Path) -> None:
    garbage = tmp_path / "garbage.pdf"
    garbage.write_bytes(b"this is not a pdf at all")

    result = run_tool(
        SPECS["pdf_repair"],
        {"input_file": str(garbage), "output_file": str(tmp_path / "out.pdf")},
    )

    assert result.status == ToolStatus.FAILED
    assert result.errors
    assert not (tmp_path / "out.pdf").exists()


def test_linearize_produces_linearized_pdf(make_pdf: MakePdf, tmp_path: Path) -> None:
    source = make_pdf(pages=4)
    target = tmp_path / "web.pdf"

    result = run_tool(
        SPECS["pdf_linearize"], {"input_file": str(source), "output_file": str(target)}
    )

    assert result.status == ToolStatus.SUCCESS, result.errors
    assert result.data == {"linearized": True, "page_count": 4}
    with pikepdf.open(target) as pdf:
        assert pdf.is_linearized


def _form_pdf(path: Path) -> Path:
    canvas = Canvas(str(path), pagesize=letter)
    canvas.drawString(72, 720, "Form page")
    canvas.acroForm.textfield(
        name="customer", value="Hello Flatten", x=72, y=600, width=200, height=24
    )
    canvas.showPage()
    canvas.save()
    return path


def test_flatten_burns_form_values_into_content(tmp_path: Path) -> None:
    source = _form_pdf(tmp_path / "form.pdf")
    target = tmp_path / "flat.pdf"

    result = run_tool(
        SPECS["pdf_flatten"], {"input_file": str(source), "output_file": str(target)}
    )

    assert result.status == ToolStatus.SUCCESS, result.errors
    assert isinstance(result.data, dict)
    assert result.data["form_fields_removed"] == 1
    assert result.data["annotations_before"] == 1
    assert result.data["annotations_after"] == 0
    with pikepdf.open(target) as pdf:
        assert "/AcroForm" not in pdf.Root
        assert "/Annots" not in pdf.pages[0].obj
    assert "Hello Flatten" in page_texts(target)[0]


def _scripted_encrypted_pdf(make_pdf: MakePdf, path: Path) -> Path:
    with pikepdf.open(make_pdf(pages=2)) as pdf:
        script = pikepdf.Dictionary(
            S=pikepdf.Name.JavaScript, JS=pikepdf.String("app.alert('hi');")
        )
        pdf.Root.OpenAction = script
        pdf.Root.Names = pikepdf.Dictionary(
            JavaScript=pikepdf.Dictionary(
                Names=pikepdf.Array([pikepdf.String("hello"), script])
            )
        )
        pdf.save(path, encryption=pikepdf.Encryption(owner="owner", user="secret"))
    return path


def test_to_pdf_a_marks_identifies_and_cleans(
    make_pdf: MakePdf, tmp_path: Path
) -> None:
    source = _scripted_encrypted_pdf(make_pdf, tmp_path / "scripted.pdf")
    target = tmp_path / "archive.pdf"

    result = run_tool(
        SPECS["pdf_to_pdf_a"],
        {"input_file": str(source), "output_file": str(target), "password": "secret"},
    )

    assert result.status == ToolStatus.SUCCESS, result.errors
    assert isinstance(result.data, dict)
    assert result.data["validated"] is False
    assert result.data["output_intent_added"] is True
    assert result.data["forbidden_actions_removed"] == 2
    assert result.data["unembedded_fonts"] == ["Helvetica"]
    assert any("NOT validated" in warning for warning in result.warnings)
    assert any("Helvetica" in warning for warning in result.warnings)
    with pikepdf.open(target) as pdf:
        assert not pdf.is_encrypted
        assert "/OpenAction" not in pdf.Root
        assert "/JavaScript" not in pdf.Root.Names
        intent = pdf.Root.OutputIntents[0]
        assert intent.S == pikepdf.Name.GTS_PDFA1
        profile = intent.DestOutputProfile
        assert isinstance(profile, pikepdf.Stream)
        assert int(profile.N) == 3
        assert profile.read_bytes()[36:40] == b"acsp"
        meta = pdf.open_metadata()
        assert meta["pdfaid:part"] == "2"
        assert meta["pdfaid:conformance"] == "B"


def test_to_pdf_a_rejects_wrong_password(make_pdf: MakePdf, tmp_path: Path) -> None:
    source = _scripted_encrypted_pdf(make_pdf, tmp_path / "locked.pdf")

    result = run_tool(
        SPECS["pdf_to_pdf_a"],
        {
            "input_file": str(source),
            "output_file": str(tmp_path / "out.pdf"),
            "password": "wrong",
        },
    )

    assert result.status == ToolStatus.FAILED
    assert result.errors
    assert "password" in result.errors[0].lower()
