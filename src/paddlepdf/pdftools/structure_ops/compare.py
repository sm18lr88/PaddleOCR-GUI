"""Two-document comparison: per-page text diff plus optional pixel diff images."""

import difflib
import json
from pathlib import Path
from typing import Annotated, Final

from PIL import Image, ImageChops
from pydantic import Field, JsonValue

from paddlepdf.pdftools.common import input_path, output_directory, output_path
from paddlepdf.pdftools.contract import PdfToolError, ToolOutcome
from paddlepdf.pdftools.pdfium import page_texts, render_page

MAX_DIFF_LINES: Final = 200
PIXEL_THRESHOLD: Final = 16
CHANGED_LUT: Final = [0] * PIXEL_THRESHOLD + [255] * (256 - PIXEL_THRESHOLD)
HIGHLIGHT: Final = (255, 0, 0)

type PageRecord = dict[str, JsonValue]


def _text_records(texts_a: list[str], texts_b: list[str]) -> list[PageRecord]:
    records: list[PageRecord] = []
    for index in range(max(len(texts_a), len(texts_b))):
        number = index + 1
        if index >= len(texts_b):
            records.append({"page": number, "status": "removed"})
            continue
        if index >= len(texts_a):
            records.append({"page": number, "status": "added"})
            continue
        lines_a = texts_a[index].splitlines()
        lines_b = texts_b[index].splitlines()
        if lines_a == lines_b:
            continue
        diff = list(
            difflib.unified_diff(
                lines_a,
                lines_b,
                fromfile=f"a/page{number}",
                tofile=f"b/page{number}",
                lineterm="",
            )
        )
        records.append(
            {
                "page": number,
                "status": "changed",
                "diff": list[JsonValue](diff[:MAX_DIFF_LINES]),
                "diff_truncated": len(diff) > MAX_DIFF_LINES,
            }
        )
    return records


def _visual_record(
    first: Image.Image, second: Image.Image, number: int, directory: Path, stem: str
) -> PageRecord | None:
    base = first.convert("RGB")
    other = second.convert("RGB")
    if other.size != base.size:
        other = other.resize(base.size)
    mask = ImageChops.difference(base, other).convert("L").point(CHANGED_LUT)
    changed = mask.histogram()[255]
    if changed == 0:
        return None
    overlay = Image.blend(base, other, 0.5)
    overlay.paste(HIGHLIGHT, mask=mask)
    target = directory / f"{stem}_diff_page{number}.png"
    overlay.save(target, "PNG")
    return {
        "page": number,
        "file": str(target),
        "changed_pixels": changed,
        "changed_ratio": round(changed / (base.width * base.height), 6),
        "bbox_pixels": list[JsonValue](mask.getbbox() or ()),
    }


def pdf_compare(
    input_file_a: Annotated[str, Field(description="Path to the first (old) PDF.")],
    input_file_b: Annotated[str, Field(description="Path to the second (new) PDF.")],
    output_file: Annotated[
        str | None,
        Field(description="Optional path for a JSON diff report (same as data)."),
    ] = None,
    output_dir: Annotated[
        str | None,
        Field(description="Directory for visual diff PNGs; required if visual_diff."),
    ] = None,
    visual_diff: Annotated[
        bool,
        Field(
            description=(
                "Also render pages both PDFs share and write a PNG per page whose "
                "pixels differ, with changes highlighted in red."
            )
        ),
    ] = False,
    dpi: Annotated[
        float, Field(gt=0, le=600, description="Render resolution for visual diff.")
    ] = 72,
    password_a: Annotated[
        str | None, Field(description="Password for the first PDF if encrypted.")
    ] = None,
    password_b: Annotated[
        str | None, Field(description="Password for the second PDF if encrypted.")
    ] = None,
) -> ToolOutcome:
    first = input_path(input_file_a)
    second = input_path(input_file_b)
    if visual_diff and output_dir is None:
        msg = "visual_diff=true needs output_dir for the diff images"
        raise PdfToolError(msg)
    texts_a = page_texts(first, password_a)
    texts_b = page_texts(second, password_b)
    text_records = _text_records(texts_a, texts_b)
    changed = {int(str(record["page"])) for record in text_records}
    files: list[str] = []
    visual_records: list[JsonValue] = []
    if visual_diff and output_dir is not None:
        directory = output_directory(output_dir)
        for index in range(min(len(texts_a), len(texts_b))):
            record = _visual_record(
                render_page(first, index, dpi, password_a),
                render_page(second, index, dpi, password_b),
                index + 1,
                directory,
                first.stem,
            )
            if record is not None:
                visual_records.append(record)
                files.append(str(record["file"]))
                changed.add(index + 1)
    changed_pages = sorted(changed)
    data: dict[str, JsonValue] = {
        "diff_detected": bool(changed_pages),
        "page_count_a": len(texts_a),
        "page_count_b": len(texts_b),
        "changed_pages": list[JsonValue](changed_pages),
        "text_differences": list[JsonValue](text_records),
        "visual_differences": visual_records if visual_diff else None,
    }
    if output_file is not None:
        report = output_path(output_file, first, second)
        report.write_text(json.dumps(data, indent=2), encoding="utf-8")
        files.insert(0, str(report))
    return ToolOutcome(output_files=tuple(files), data=data)
