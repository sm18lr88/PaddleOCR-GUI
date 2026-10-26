import base64
import json
from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING, cast

import pikepdf
import pytest
from openpyxl import Workbook
from PIL import Image

from paddlepdf.pdftools.contract import ToolSpec, ToolStatus
from paddlepdf.pdftools.create import TOOLS
from paddlepdf.pdftools.pdfium import page_texts
from paddlepdf.pdftools.runner import run_tool

if TYPE_CHECKING:
    from openpyxl.worksheet.worksheet import Worksheet

SPECS = {spec.name: spec for spec in TOOLS}


def _spec(name: str) -> ToolSpec:
    return SPECS[name]


def _png_bytes(size: tuple[int, int], color: str) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", size, color).save(buffer, "PNG")
    return buffer.getvalue()


def _media_box(path: Path, index: int = 0) -> tuple[float, ...]:
    with pikepdf.open(path) as pdf:
        return tuple(float(value) for value in pdf.pages[index].mediabox)


def _image_count(path: Path, index: int = 0) -> int:
    with pikepdf.open(path) as pdf:
        return len(pdf.pages[index].get_images())


def test_convert_html_renders_text_image_and_page_size(tmp_path: Path) -> None:
    (tmp_path / "logo.png").write_bytes(_png_bytes((40, 20), "red"))
    source = tmp_path / "report.html"
    source.write_text(
        """<html><head><title>t</title></head><body>
<h1>Quarterly Report</h1><p>Revenue grew.</p><img src="logo.png">
</body></html>""",
        encoding="utf-8",
    )
    target = tmp_path / "out" / "report.pdf"

    result = run_tool(
        _spec("pdf_convert_html"),
        {
            "input_file": str(source),
            "output_file": str(target),
            "preset": "elegant",
            "page_size": "Letter",
        },
    )

    assert result.status is ToolStatus.SUCCESS, result.errors
    assert result.output_files == (str(target),)
    assert result.data == {"page_count": 1}
    assert _media_box(target) == (0, 0, 612, 792)
    assert "Quarterly Report" in page_texts(target)[0]
    assert _image_count(target) == 1


def test_convert_html_fragment_defaults_to_a4_and_warns_on_missing_image(
    tmp_path: Path,
) -> None:
    source = tmp_path / "fragment.html"
    source.write_text('<p>Fragment body</p><img src="absent.png">', encoding="utf-8")
    target = tmp_path / "fragment.pdf"

    result = run_tool(
        _spec("pdf_convert_html"),
        {
            "input_file": str(source),
            "output_file": str(target),
            "orientation": "landscape",
        },
    )

    assert result.status is ToolStatus.SUCCESS, result.errors
    width, height = _media_box(target)[2:]
    assert (round(width), round(height)) == (842, 595)
    assert "Fragment body" in page_texts(target)[0]
    assert any("absent.png" in warning for warning in result.warnings)


def test_convert_markdown_renders_headings_and_tables(tmp_path: Path) -> None:
    source = tmp_path / "notes.md"
    source.write_text(
        """# Release Notes

| Name | Score |
|------|-------|
| Alpha | 42 |

```
fenced code line
```
""",
        encoding="utf-8",
    )
    target = tmp_path / "notes.pdf"

    result = run_tool(
        _spec("pdf_convert_markdown"),
        {"input_file": str(source), "output_file": str(target), "preset": "compact"},
    )

    assert result.status is ToolStatus.SUCCESS, result.errors
    text = page_texts(target)[0]
    for expected in ("Release Notes", "Alpha", "42", "fenced code line"):
        assert expected in text


def test_convert_excel_csv_renders_header_and_rows(tmp_path: Path) -> None:
    source = tmp_path / "people.csv"
    source.write_text("name,city\nAda,London\nGrace,Arlington\n", encoding="utf-8")
    target = tmp_path / "people.pdf"

    result = run_tool(
        _spec("pdf_convert_excel"),
        {"input_file": str(source), "output_file": str(target)},
    )

    assert result.status is ToolStatus.SUCCESS, result.errors
    assert result.data == {"page_count": 1, "data_rows": 2}
    text = page_texts(target)[0]
    for expected in ("name", "city", "Ada", "Arlington"):
        assert expected in text


def test_convert_excel_xlsx_renders_every_sheet(tmp_path: Path) -> None:
    workbook = Workbook()
    first = workbook.active
    assert first is not None
    first.title = "Inventory"
    first.append(["item", "qty"])
    first.append(["bolts", 3.0])
    second = cast("Worksheet", workbook.create_sheet("Prices"))
    second.append(["item", "price"])
    second.append(["nuts", 1.25])
    source = tmp_path / "book.xlsx"
    workbook.save(source)
    target = tmp_path / "book.pdf"

    result = run_tool(
        _spec("pdf_convert_excel"),
        {"input_file": str(source), "output_file": str(target), "preset": "branded"},
    )

    assert result.status is ToolStatus.SUCCESS, result.errors
    text = " ".join(page_texts(target))
    for expected in ("Inventory", "Prices", "bolts", "nuts", "1.25"):
        assert expected in text
    assert "3.0" not in text


def test_convert_excel_rejects_unsupported_suffix(tmp_path: Path) -> None:
    source = tmp_path / "legacy.xls"
    source.write_bytes(b"not a workbook")

    result = run_tool(
        _spec("pdf_convert_excel"),
        {"input_file": str(source), "output_file": str(tmp_path / "legacy.pdf")},
    )

    assert result.status is ToolStatus.FAILED
    assert result.errors
    assert ".xls" in result.errors[0]


def test_json_to_pdf_places_text_and_images(tmp_path: Path) -> None:
    (tmp_path / "side.png").write_bytes(_png_bytes((8, 8), "blue"))
    inline = base64.b64encode(_png_bytes((4, 4), "green")).decode()
    document = {
        "document_name": "Field Notes",
        "pages": [
            {
                "page_number": 1,
                "text": "First page line\nSecond line",
                "images": [
                    {
                        "id": "inline",
                        "bbox": [10, 10, 100, 100],
                        "base64_data": f"data:image/png;base64,{inline}",
                    },
                    {"id": "file", "bbox": [200, 10, 260, 70], "file_path": "side.png"},
                    {"id": "floating", "base64_data": inline},
                ],
            },
            {"page_number": 2, "text": "Closing page"},
        ],
    }
    source = tmp_path / "doc.json"
    source.write_text(json.dumps(document), encoding="utf-8")
    target = tmp_path / "doc.pdf"

    result = run_tool(
        _spec("json_to_pdf"), {"input_file": str(source), "output_file": str(target)}
    )

    assert result.status is ToolStatus.SUCCESS, result.errors
    assert result.data == {
        "document_name": "Field Notes",
        "source_pages": 2,
        "page_count": 2,
        "images_drawn": 2,
    }
    assert any("floating" in warning for warning in result.warnings)
    texts = page_texts(target)
    assert "First page line" in texts[0]
    assert "Second line" in texts[0]
    assert "Closing page" in texts[1]
    assert _media_box(target, 1) == (0, 0, 612, 792)
    assert _image_count(target) == 2
    with pikepdf.open(target) as pdf:
        assert str(pdf.docinfo["/Title"]) == "Field Notes"


def test_json_to_pdf_continues_long_text_on_new_sheets(tmp_path: Path) -> None:
    lines = "\n".join(f"row {number}" for number in range(1, 101))
    source = tmp_path / "long.json"
    source.write_text(
        json.dumps(
            {"document_name": "long", "pages": [{"page_number": 1, "text": lines}]}
        ),
        encoding="utf-8",
    )
    target = tmp_path / "long.pdf"

    result = run_tool(
        _spec("json_to_pdf"), {"input_file": str(source), "output_file": str(target)}
    )

    assert result.status is ToolStatus.SUCCESS, result.errors
    texts = page_texts(target)
    assert len(texts) == 3
    assert "row 100" in texts[-1]


@pytest.mark.parametrize(
    "payload",
    ['{"pages": []}', "not json", '{"document_name": "x", "pages": []}'],
)
def test_json_to_pdf_rejects_invalid_documents(tmp_path: Path, payload: str) -> None:
    source = tmp_path / "bad.json"
    source.write_text(payload, encoding="utf-8")
    target = tmp_path / "bad.pdf"

    result = run_tool(
        _spec("json_to_pdf"), {"input_file": str(source), "output_file": str(target)}
    )

    assert result.status is ToolStatus.FAILED
    assert result.errors
    assert not target.exists()
