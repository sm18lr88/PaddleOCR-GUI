from __future__ import annotations

APP_STYLESHEET = """
QWidget {
    background: #08090a;
    color: #f7f8f8;
    font-family: "Segoe UI", "SF Pro Display", Arial, sans-serif;
    font-size: 10pt;
}
QMainWindow {
    background: #08090a;
}
QGroupBox {
    background: rgba(255, 255, 255, 0.02);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 8px;
    color: #d0d6e0;
    font-weight: 510;
    margin-top: 18px;
    padding: 14px 12px 12px 12px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 5px;
    color: #8a8f98;
}
QLabel {
    background: transparent;
    color: #d0d6e0;
}
QLabel#AppTitle {
    color: #f7f8f8;
    font-size: 20pt;
    font-weight: 590;
}
QLabel#AppSubtitle,
QLabel#StatusLabel {
    color: #8a8f98;
}
QListWidget,
QPlainTextEdit {
    background: #0f1011;
    border: 1px solid rgba(255, 255, 255, 0.10);
    border-radius: 6px;
    color: #d0d6e0;
    padding: 10px;
    selection-background-color: #5e6ad2;
    selection-color: #f7f8f8;
}
QListWidget#DocumentQueue {
    min-height: 76px;
    max-height: 96px;
}
QLineEdit,
QComboBox {
    background: #0f1011;
    border: 1px solid rgba(255, 255, 255, 0.10);
    border-radius: 6px;
    color: #f7f8f8;
    min-height: 28px;
    padding: 4px 8px;
    selection-background-color: #5e6ad2;
}
QLineEdit:focus,
QComboBox:focus,
QListWidget:focus,
QPlainTextEdit:focus {
    border: 1px solid #7170ff;
}
QComboBox::drop-down {
    border: 0;
    width: 24px;
}
QComboBox QAbstractItemView {
    background: #15171a;
    border: 1px solid rgba(255, 255, 255, 0.10);
    color: #f7f8f8;
    selection-background-color: #1d2025;
}
QPushButton {
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid rgba(255, 255, 255, 0.10);
    border-radius: 6px;
    color: #d0d6e0;
    font-weight: 510;
    max-width: 220px;
    min-height: 30px;
    padding: 5px 12px;
}
QPushButton:hover {
    background: #1d2025;
    color: #f7f8f8;
}
QPushButton:pressed {
    background: #15171a;
}
QPushButton#PrimaryButton {
    background: #5e6ad2;
    border: 1px solid #7170ff;
    color: #f7f8f8;
}
QPushButton#PrimaryButton:hover {
    background: #7170ff;
}
QPushButton#PrimaryButton:pressed {
    background: #4d58b8;
}
QPushButton:disabled {
    background: rgba(255, 255, 255, 0.02);
    border-color: rgba(255, 255, 255, 0.06);
    color: #62666d;
}
QCheckBox {
    spacing: 8px;
    color: #d0d6e0;
    background: transparent;
}
QCheckBox::indicator {
    background: #0f1011;
    border: 1px solid rgba(255, 255, 255, 0.14);
    border-radius: 4px;
    height: 14px;
    width: 14px;
}
QCheckBox::indicator:checked {
    background: #5e6ad2;
    border: 1px solid #7170ff;
}
QProgressBar {
    background: #0f1011;
    border: 1px solid rgba(255, 255, 255, 0.10);
    border-radius: 6px;
    color: #d0d6e0;
    min-height: 14px;
    text-align: center;
}
QProgressBar::chunk {
    background: #5e6ad2;
    border-radius: 5px;
}
QMessageBox {
    background: #08090a;
}
"""
