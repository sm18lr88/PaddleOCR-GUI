from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PySide6.QtWidgets import (
        QCheckBox,
        QComboBox,
        QGridLayout,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QListWidget,
        QPlainTextEdit,
        QProgressBar,
        QPushButton,
        QWidget,
    )

    from paddlepdf.i18n import UiLanguage


@dataclass(frozen=True, slots=True)
class LayoutActions:
    initial_language: UiLanguage
    output_dir: Path
    apply_language: Callable[[str], None]
    select_files: Callable[[], None]
    select_output_folder: Callable[[], None]
    start_conversion: Callable[[], None]
    open_output_folder: Callable[[], None]


@dataclass(frozen=True, slots=True)
class LayoutWidgets:
    root: QWidget
    file_list: QListWidget
    language_box: QComboBox
    language_label: QLabel
    documents_label: QLabel
    select_files_button: QPushButton
    output_folder: QLineEdit
    output_label: QLabel
    select_output_button: QPushButton
    orientation_box: QCheckBox
    unwarp_box: QCheckBox
    layout_box: QCheckBox
    format_box: QComboBox
    profile_box: QComboBox
    device_box: QComboBox
    format_label: QLabel
    profile_label: QLabel
    device_label: QLabel
    knobs_label: QLabel
    progress_bar: QProgressBar
    status_label: QLabel
    convert_button: QPushButton
    open_folder_button: QPushButton
    activity_label: QLabel
    log: QPlainTextEdit


@dataclass(frozen=True, slots=True)
class HeaderWidgets:
    layout: QHBoxLayout
    language_box: QComboBox
    language_label: QLabel


@dataclass(frozen=True, slots=True)
class DocumentWidgets:
    header: QHBoxLayout
    label: QLabel
    file_list: QListWidget
    select_files_button: QPushButton


@dataclass(frozen=True, slots=True)
class OutputWidgets:
    row: QHBoxLayout
    label: QLabel
    output_folder: QLineEdit
    select_output_button: QPushButton


@dataclass(frozen=True, slots=True)
class SettingsWidgets:
    grid: QGridLayout
    orientation_box: QCheckBox
    unwarp_box: QCheckBox
    layout_box: QCheckBox
    format_box: QComboBox
    profile_box: QComboBox
    device_box: QComboBox
    format_label: QLabel
    profile_label: QLabel
    device_label: QLabel
    knobs_label: QLabel


@dataclass(frozen=True, slots=True)
class RunWidgets:
    row: QHBoxLayout
    progress_bar: QProgressBar
    status_label: QLabel
    convert_button: QPushButton
    open_folder_button: QPushButton
