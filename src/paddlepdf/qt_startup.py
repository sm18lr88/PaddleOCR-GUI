from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PySide6.QtWidgets import QApplication


def normalize_application_font(app: QApplication) -> None:
    font = app.font()
    if font.pointSize() <= 0:
        font.setPointSize(10)
        app.setFont(font)
