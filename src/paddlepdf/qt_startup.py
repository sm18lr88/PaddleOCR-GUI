from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PySide6.QtWidgets import QApplication


def configure_qt_environment() -> None:
    if sys.platform != "win32":
        return
    windows_font_dir = Path(os.environ.get("WINDIR", "C:\\Windows")) / "Fonts"
    if windows_font_dir.exists():
        os.environ.setdefault("QT_QPA_FONTDIR", str(windows_font_dir))


def normalize_application_font(app: QApplication) -> None:
    font = app.font()
    if font.pointSize() <= 0:
        font.setPointSize(10)
        app.setFont(font)
