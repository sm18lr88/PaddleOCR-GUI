import json
from collections.abc import Callable, Mapping
from pathlib import Path

import pikepdf
import pytest

from paddlepdf.pdftools import pdfium
from paddlepdf.pdftools.contract import ToolResult, ToolSpec, ToolStatus
from paddlepdf.pdftools.runner import run_tool
from paddlepdf.pdftools.workflows import TOOLS

type MakePdf = Callable[..., Path]

LOCK_CODE = "pw"
SPECS = {spec.name: spec for spec in TOOLS}


def run_workflow(params: Mapping[str, object]) -> ToolResult:
    return run_tool(SPECS["document_workflow"], params)


def assert_failed(result: ToolResult, fragment: str) -> None:
    assert result.status is ToolStatus.FAILED
    assert result.errors
    assert fragment in result.errors[0]


def test_tools_expose_both_names() -> None:
    assert sorted(SPECS) == ["document_workflow", "list_workflows"]
    assert all(isinstance(spec, ToolSpec) for spec in TOOLS)


def test_list_workflows_returns_presets() -> None:
    result = run_tool(SPECS["list_workflows"], {})
    assert result.status is ToolStatus.SUCCESS
    assert isinstance(result.data, list)
    ids = [item["id"] for item in result.data if isinstance(item, dict)]
    assert ids == [
        "preset-legal-discovery",
        "preset-clean-scan",
        "preset-redact-protect",
    ]


def test_legal_discovery_preset_numbers_and_watermarks(
    make_pdf: MakePdf, tmp_path: Path
) -> None:
    source = make_pdf()
    out = tmp_path / "out" / "legal.pdf"
    result = run_workflow(
        {
            "input_file": str(source),
            "output_file": str(out),
            "preset": "legal-discovery",
        }
    )
    assert result.status is ToolStatus.SUCCESS, result.errors
    assert result.output_files == (str(out),)
    assert isinstance(result.data, dict)
    assert result.data["steps_completed"] == 3
    texts = pdfium.page_texts(out)
    assert len(texts) == 3
    assert "CONFIDENTIAL" in texts[0]
    assert "000001" in texts[0]
    assert "000003" in texts[2]
    assert list(out.parent.glob(".workflow-*")) == []


def test_clean_scan_preset_adds_page_numbers(make_pdf: MakePdf, tmp_path: Path) -> None:
    out = tmp_path / "clean.pdf"
    result = run_workflow(
        {
            "input_file": str(make_pdf()),
            "output_file": str(out),
            "preset": "preset-clean-scan",
        }
    )
    assert result.status is ToolStatus.SUCCESS, result.errors
    assert "Page 1 of 3" in pdfium.page_texts(out)[0]


def test_redact_protect_preset_with_step_params_encrypts(
    make_pdf: MakePdf, tmp_path: Path
) -> None:
    out = tmp_path / "secure.pdf"
    result = run_workflow(
        {
            "input_file": str(make_pdf(text="secret-token")),
            "output_file": str(out),
            "preset": "redact-protect",
            "step_params": {
                "pdf_redact": {"search_text": "secret-token"},
                "pdf_encrypt": {"user_password": LOCK_CODE},
            },
        }
    )
    assert result.status is ToolStatus.SUCCESS, result.errors
    with pytest.raises(pikepdf.PasswordError):
        pikepdf.open(out)
    with pikepdf.open(out, password=LOCK_CODE) as pdf:
        assert pdf.is_encrypted
        assert len(pdf.pages) == 3


def test_custom_steps_accept_unprefixed_names_and_param_aliases(
    make_pdf: MakePdf, tmp_path: Path
) -> None:
    out = tmp_path / "custom.pdf"
    result = run_workflow(
        {
            "input_file": str(make_pdf()),
            "output_file": str(out),
            "steps": [
                {"tool": "rotate", "params": {"angle": 90}},
                {"tool": "bates", "params": {"prefix": "X-", "start": 7}},
            ],
        }
    )
    assert result.status is ToolStatus.SUCCESS, result.errors
    with pikepdf.open(out) as pdf:
        assert all(int(page.get("/Rotate", 0)) == 90 for page in pdf.pages)
    assert "000007" in pdfium.page_texts(out)[0]


def test_recipe_json_string_with_operation_id(
    make_pdf: MakePdf, tmp_path: Path
) -> None:
    out = tmp_path / "recipe.pdf"
    recipe = json.dumps(
        {
            "id": "r1",
            "name": "Rotate recipe",
            "steps": [{"operationId": "pdf_rotate", "params": {"angle": 180}}],
        }
    )
    result = run_workflow(
        {"input_file": str(make_pdf()), "output_file": str(out), "recipe": recipe}
    )
    assert result.status is ToolStatus.SUCCESS, result.errors
    assert isinstance(result.data, dict)
    assert result.data["workflow_name"] == "Rotate recipe"
    with pikepdf.open(out) as pdf:
        assert int(pdf.pages[0].get("/Rotate", 0)) == 180


def test_failing_step_stops_workflow_and_names_step(
    make_pdf: MakePdf, tmp_path: Path
) -> None:
    out = tmp_path / "never.pdf"
    result = run_workflow(
        {
            "input_file": str(make_pdf()),
            "output_file": str(out),
            "preset": "redact-protect",
        }
    )
    assert_failed(result, "Step 1 (pdf_redact) failed")
    assert not out.exists()


def test_recursive_and_reading_tools_are_refused(
    make_pdf: MakePdf, tmp_path: Path
) -> None:
    source = make_pdf()
    for name, fragment in (
        ("document_workflow", "recursion"),
        ("list_workflows", "recursion"),
        ("pdf_extract_text", "convert_documents"),
        ("pdf_nonexistent", "Unknown workflow tool"),
    ):
        result = run_workflow(
            {
                "input_file": str(source),
                "output_file": str(tmp_path / "x.pdf"),
                "steps": [{"tool": name}],
            }
        )
        assert_failed(result, fragment)


def test_requires_exactly_one_source_and_known_preset(
    make_pdf: MakePdf, tmp_path: Path
) -> None:
    base = {"input_file": str(make_pdf()), "output_file": str(tmp_path / "x.pdf")}
    assert_failed(run_workflow(base), "exactly one")
    assert_failed(run_workflow({**base, "preset": "nope"}), "Preset not found")
