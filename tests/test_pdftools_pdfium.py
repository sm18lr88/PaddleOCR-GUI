from collections.abc import Callable
from pathlib import Path

from paddlepdf.pdftools.pdfium import (
    find_text_boxes,
    page_count,
    page_texts,
    render_page,
)

type MakePdf = Callable[..., Path]


def test_pdfium_adapter_reads_renders_and_locates_text(make_pdf: MakePdf) -> None:
    source = make_pdf(pages=2, text="CONFIDENTIAL token")

    image = render_page(source, 1, dpi=72)
    boxes = find_text_boxes(source, "confidential")

    assert page_count(source) == 2
    assert "Page 2" in page_texts(source)[1]
    assert image.size == (612, 792)
    assert sorted(boxes) == [0, 1]
    left, bottom, right, top = boxes[0][0]
    assert left < right
    assert bottom < top
