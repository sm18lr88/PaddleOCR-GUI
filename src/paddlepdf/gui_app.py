from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from paddlepdf.gui import PaddlePdfWindow
from paddlepdf.qt_startup import normalize_application_font
from paddlepdf.theme import APP_STYLESHEET


def main() -> None:
    app = QApplication(sys.argv)
    normalize_application_font(app)
    app.setStyleSheet(APP_STYLESHEET)
    window = PaddlePdfWindow()
    window.show()
    raise SystemExit(app.exec())
