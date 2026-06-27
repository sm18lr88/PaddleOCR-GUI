from __future__ import annotations

APP_STYLESHEET = """
QWidget {
    background: #12151c;
    color: #eef2ff;
    font-size: 14px;
}
QMainWindow {
    background: #12151c;
}
QListWidget,
QLineEdit,
QPlainTextEdit,
QComboBox {
    background: #1a1f2b;
    border: 1px solid #31384a;
    border-radius: 8px;
    color: #f8fafc;
    padding: 8px;
    selection-background-color: #4f7cff;
}
QPushButton {
    background: #4f7cff;
    border: 0;
    border-radius: 9px;
    color: white;
    font-weight: 600;
    padding: 9px 14px;
}
QPushButton:hover {
    background: #6f93ff;
}
QPushButton:pressed {
    background: #355bd6;
}
QPushButton:disabled {
    background: #303747;
    color: #8991a5;
}
QCheckBox {
    spacing: 8px;
}
QProgressBar {
    background: #1a1f2b;
    border: 1px solid #31384a;
    border-radius: 8px;
    color: #eef2ff;
    min-height: 18px;
    text-align: center;
}
QProgressBar::chunk {
    background: #4f7cff;
    border-radius: 8px;
}
QMessageBox {
    background: #12151c;
}
"""
