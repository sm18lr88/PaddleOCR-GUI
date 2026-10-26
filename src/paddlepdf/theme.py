from __future__ import annotations

APP_STYLESHEET = """
QWidget {
    background: #202327;
    color: #eceff3;
    font-family: "Segoe UI Variable Text", "Segoe UI", "SF Pro Display",
        Arial, sans-serif;
    font-size: 10pt;
}
QMainWindow {
    background: #202327;
}
QGroupBox {
    background: transparent;
    border: 0;
    margin: 0;
    padding: 0;
}
QLabel {
    background: transparent;
    color: #eceff3;
}
QLabel#AppTitle {
    color: #eceff3;
    font-size: 17pt;
    font-weight: 700;
}
QLabel#SectionTitle,
QLabel#InlineLabel,
QLabel#StatusLabel {
    color: #b3bac5;
}
QLabel#SectionTitle {
    font-size: 9pt;
    font-weight: 700;
}
QListWidget,
QPlainTextEdit {
    background: #282d33;
    border: 1px solid #444c57;
    border-radius: 6px;
    color: #eceff3;
    padding: 6px 8px;
    selection-background-color: #7890ae;
    selection-color: #ffffff;
}
QListWidget#DocumentQueue {
    min-height: 44px;
    max-height: 52px;
}
QLineEdit,
QComboBox {
    background: #282d33;
    border: 1px solid #444c57;
    border-radius: 6px;
    color: #eceff3;
    min-height: 26px;
    padding: 4px 8px;
    selection-background-color: #7890ae;
}
QLineEdit:focus,
QComboBox:focus,
QListWidget:focus,
QPlainTextEdit:focus {
    border: 1px solid #7890ae;
}
QComboBox::drop-down {
    border: 0;
    width: 24px;
}
QComboBox QAbstractItemView {
    background: #282d33;
    border: 1px solid #444c57;
    color: #eceff3;
    selection-background-color: #39404a;
}
QPushButton {
    background: #30363e;
    border: 1px solid #30363e;
    border-radius: 6px;
    color: #eceff3;
    font-weight: 600;
    max-width: 220px;
    min-height: 28px;
    padding: 4px 12px;
}
QPushButton:hover {
    background: #39404a;
    border-color: #39404a;
    color: #ffffff;
}
QPushButton:pressed {
    background: #5f7899;
}
QPushButton#PrimaryButton {
    background: #7890ae;
    border: 1px solid #7890ae;
    color: #ffffff;
}
QPushButton#PrimaryButton:hover {
    background: #8ba1bc;
    border-color: #8ba1bc;
}
QPushButton#PrimaryButton:pressed {
    background: #5f7899;
}
QPushButton:disabled {
    background: #282d33;
    border-color: #353c45;
    color: #7d8794;
}
QCheckBox {
    spacing: 8px;
    color: #eceff3;
    background: transparent;
}
QCheckBox::indicator {
    background: #282d33;
    border: 1px solid #444c57;
    border-radius: 4px;
    height: 14px;
    width: 14px;
}
QCheckBox::indicator:checked {
    background: #7890ae;
    border: 1px solid #8ba1bc;
}
QProgressBar {
    background: #282d33;
    border: 1px solid #444c57;
    border-radius: 7px;
    color: #eceff3;
    min-height: 16px;
    text-align: center;
}
QProgressBar::chunk {
    background: #7890ae;
    border-radius: 5px;
}
QFrame#Divider {
    color: #353c45;
}
QMessageBox {
    background: #202327;
}
"""
