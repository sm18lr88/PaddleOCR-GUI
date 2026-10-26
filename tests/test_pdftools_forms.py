from collections.abc import Callable
from pathlib import Path

import pikepdf
import pytest
from pydantic import JsonValue

from paddlepdf.pdftools.contract import ToolResult, ToolStatus
from paddlepdf.pdftools.forms import TOOLS
from paddlepdf.pdftools.runner import run_tool

type MakePdf = Callable[..., Path]

SPECS = {spec.name: spec for spec in TOOLS}
READ_FORM = SPECS["pdf_read_form"]
FILL_FORM = SPECS["pdf_fill_form"]
CREATE_FIELD = SPECS["pdf_create_form_field"]


def read_fields(result: ToolResult) -> list[dict[str, JsonValue]]:
    data = result.data
    assert isinstance(data, dict)
    raw_fields = data["fields"]
    assert isinstance(raw_fields, list)
    fields: list[dict[str, JsonValue]] = []
    for item in raw_fields:
        assert isinstance(item, dict)
        fields.append(item)
    return fields


def test_tools_registered() -> None:
    assert sorted(SPECS) == ["pdf_create_form_field", "pdf_fill_form", "pdf_read_form"]


def test_create_text_field_then_read_it_back(make_pdf: MakePdf, tmp_path: Path) -> None:
    source = make_pdf()
    output = tmp_path / "with_field.pdf"

    result = run_tool(
        CREATE_FIELD,
        {
            "input_file": str(source),
            "output_file": str(output),
            "field_name": "FirstName",
            "field_type": "text",
            "page": 1,
            "rect": (10.0, 20.0, 210.0, 40.0),
        },
    )

    assert result.status == ToolStatus.SUCCESS
    assert result.output_files == (str(output),)

    read_result = run_tool(READ_FORM, {"input_file": str(output)})
    assert read_result.status == ToolStatus.SUCCESS
    fields = read_fields(read_result)
    assert len(fields) == 1
    assert fields[0]["name"] == "FirstName"
    assert fields[0]["type"] == "text"
    assert fields[0]["page"] == 1
    assert fields[0]["value"] is None


def test_create_checkbox_field_defaults_unchecked(
    make_pdf: MakePdf, tmp_path: Path
) -> None:
    source = make_pdf()
    output = tmp_path / "with_checkbox.pdf"

    result = run_tool(
        CREATE_FIELD,
        {
            "input_file": str(source),
            "output_file": str(output),
            "field_name": "Agree",
            "field_type": "checkbox",
            "page": 1,
            "rect": (10.0, 20.0, 30.0, 40.0),
        },
    )

    assert result.status == ToolStatus.SUCCESS

    read_result = run_tool(READ_FORM, {"input_file": str(output)})
    fields = read_fields(read_result)
    assert fields[0]["type"] == "checkbox"
    assert fields[0]["value"] is False


def test_fill_form_sets_text_and_checkbox_values(
    make_pdf: MakePdf, tmp_path: Path
) -> None:
    source = make_pdf()
    with_text = tmp_path / "text_field.pdf"
    run_tool(
        CREATE_FIELD,
        {
            "input_file": str(source),
            "output_file": str(with_text),
            "field_name": "FullName",
            "field_type": "text",
            "page": 1,
            "rect": (10.0, 20.0, 210.0, 40.0),
        },
    )
    with_checkbox = tmp_path / "both_fields.pdf"
    run_tool(
        CREATE_FIELD,
        {
            "input_file": str(with_text),
            "output_file": str(with_checkbox),
            "field_name": "Agree",
            "field_type": "checkbox",
            "page": 1,
            "rect": (10.0, 50.0, 30.0, 70.0),
        },
    )

    filled = tmp_path / "filled.pdf"
    fill_result = run_tool(
        FILL_FORM,
        {
            "input_file": str(with_checkbox),
            "output_file": str(filled),
            "values": {"FullName": "Jane Doe", "Agree": True},
        },
    )

    assert fill_result.status == ToolStatus.SUCCESS
    assert fill_result.output_files == (str(filled),)

    read_result = run_tool(READ_FORM, {"input_file": str(filled)})
    fields_by_name: dict[JsonValue, dict[str, JsonValue]] = {
        field["name"]: field for field in read_fields(read_result)
    }
    assert fields_by_name["FullName"]["value"] == "Jane Doe"
    assert fields_by_name["Agree"]["value"] is True

    with pikepdf.open(filled) as pdf:
        assert pdf.acroform.exists
        for field in pdf.acroform.fields:
            if field.fully_qualified_name == "FullName":
                for annotation in pdf.acroform.get_annotations_for_field(field):
                    assert annotation.get_appearance_stream(pikepdf.Name.N) is not None


def test_read_form_on_pdf_without_fields_returns_empty_list(make_pdf: MakePdf) -> None:
    source = make_pdf()
    result = run_tool(READ_FORM, {"input_file": str(source)})
    assert result.status == ToolStatus.SUCCESS
    assert result.data == {"fields": []}


def test_fill_form_missing_field_fails(make_pdf: MakePdf, tmp_path: Path) -> None:
    source = make_pdf()
    with_field = tmp_path / "with_field.pdf"
    run_tool(
        CREATE_FIELD,
        {
            "input_file": str(source),
            "output_file": str(with_field),
            "field_name": "FirstName",
            "field_type": "text",
            "page": 1,
            "rect": (10.0, 20.0, 210.0, 40.0),
        },
    )
    output = tmp_path / "out.pdf"

    result = run_tool(
        FILL_FORM,
        {
            "input_file": str(with_field),
            "output_file": str(output),
            "values": {"DoesNotExist": "value"},
        },
    )

    assert result.status == ToolStatus.FAILED
    assert result.errors
    assert not output.exists()


def test_fill_form_without_acroform_fails(make_pdf: MakePdf, tmp_path: Path) -> None:
    source = make_pdf()
    output = tmp_path / "out.pdf"

    result = run_tool(
        FILL_FORM,
        {"input_file": str(source), "output_file": str(output), "values": {"X": "y"}},
    )

    assert result.status == ToolStatus.FAILED
    assert result.errors


def test_create_form_field_bad_page_fails(make_pdf: MakePdf, tmp_path: Path) -> None:
    source = make_pdf(pages=1)
    output = tmp_path / "out.pdf"

    result = run_tool(
        CREATE_FIELD,
        {
            "input_file": str(source),
            "output_file": str(output),
            "field_name": "X",
            "field_type": "text",
            "page": 5,
            "rect": (0.0, 0.0, 10.0, 10.0),
        },
    )

    assert result.status == ToolStatus.FAILED
    assert result.errors


def test_read_form_missing_input_fails(tmp_path: Path) -> None:
    result = run_tool(READ_FORM, {"input_file": str(tmp_path / "missing.pdf")})
    assert result.status == ToolStatus.FAILED
    assert result.errors


@pytest.mark.parametrize("field_type", ["text", "checkbox"])
def test_create_form_field_output_differs_from_input(
    make_pdf: MakePdf, tmp_path: Path, field_type: str
) -> None:
    source = make_pdf()
    output = tmp_path / f"{field_type}.pdf"

    result = run_tool(
        CREATE_FIELD,
        {
            "input_file": str(source),
            "output_file": str(output),
            "field_name": "Field",
            "field_type": field_type,
            "page": 1,
            "rect": (0.0, 0.0, 50.0, 20.0),
        },
    )

    assert result.status == ToolStatus.SUCCESS
    assert output.is_file()
