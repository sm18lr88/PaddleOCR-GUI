from collections.abc import Callable
from pathlib import Path

import pytest
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen.canvas import Canvas

type MakePdf = Callable[..., Path]


@pytest.fixture
def make_pdf(tmp_path: Path) -> MakePdf:
    """Write a real text PDF whose page N shows "Page N" (plus optional extra text)."""

    def build(
        name: str = "sample.pdf",
        pages: int = 3,
        size: tuple[float, float] = letter,
        text: str = "",
    ) -> Path:
        path = tmp_path / name
        canvas = Canvas(str(path), pagesize=size)
        for number in range(1, pages + 1):
            canvas.setFont("Helvetica", 14)
            canvas.drawString(72, size[1] - 72, f"Page {number}")
            if text:
                canvas.drawString(72, size[1] - 100, text)
            canvas.showPage()
        canvas.save()
        return path

    return build
