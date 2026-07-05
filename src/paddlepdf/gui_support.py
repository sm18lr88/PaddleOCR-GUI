from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGroupBox,
    QLayout,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from paddlepdf.models import (
    AgentRunReport,
    ConversionRequest,
    DeviceChoice,
    OutputFormat,
    ProgressEvent,
    QualityProfile,
    VlBackend,
)
from paddlepdf.ocr_service import PaddleDocumentConverter
from paddlepdf.planning import SUPPORTED_INPUT_SUFFIXES

if TYPE_CHECKING:
    from paddlepdf.i18n import UiLanguage


class ConversionWorker(QObject):
    progress = Signal(int, int, str, str)
    finished = Signal(AgentRunReport)

    def __init__(self, request: ConversionRequest) -> None:
        super().__init__()
        self._request = request

    @Slot()
    def run(self) -> None:
        converter = PaddleDocumentConverter()

        def progress(event: ProgressEvent) -> None:
            self.progress.emit(
                event.index,
                event.total,
                event.current_file.name,
                event.message,
            )

        self.finished.emit(converter.convert(self._request, progress=progress))


def combo_box(
    enum_type: type[
        OutputFormat | QualityProfile | DeviceChoice | VlBackend | UiLanguage
    ],
    selected: OutputFormat | QualityProfile | DeviceChoice | VlBackend | UiLanguage,
) -> QComboBox:
    combo = QComboBox()
    for item in enum_type:
        combo.addItem(item.value)
    combo.setCurrentText(selected.value)
    return combo


def quality_profile_box(
    orientation_box: QCheckBox,
    unwarp_box: QCheckBox,
    layout_box: QCheckBox,
) -> QComboBox:
    profile_box = combo_box(QualityProfile, QualityProfile.BALANCED)

    def update_profile(value: str) -> None:
        apply_profile_to_checks(
            QualityProfile(value), orientation_box, unwarp_box, layout_box
        )

    profile_box.currentTextChanged.connect(update_profile)
    return profile_box


def apply_profile_to_checks(
    profile: QualityProfile,
    orientation_box: QCheckBox,
    unwarp_box: QCheckBox,
    layout_box: QCheckBox,
) -> None:
    match profile:
        case QualityProfile.FAST | QualityProfile.BALANCED:
            orientation_box.setChecked(False)
            unwarp_box.setChecked(False)
            layout_box.setChecked(True)
        case QualityProfile.QUALITY:
            orientation_box.setChecked(True)
            unwarp_box.setChecked(True)
            layout_box.setChecked(True)


def open_output_folder(output_dir: Path) -> None:
    QDesktopServices.openUrl(QUrl.fromLocalFile(str(output_dir)))


def set_running_controls(
    convert_button: QPushButton,
    open_folder_button: QPushButton,
    latest_output_dir: Path,
    running: bool,
) -> None:
    convert_button.setEnabled(not running)
    open_folder_button.setEnabled((not running) and latest_output_dir.exists())


def append_report_to_log(log: QPlainTextEdit, report: AgentRunReport) -> None:
    for document in report.documents:
        log.appendPlainText(f"{document.input_file.name}: {document.status.value}")
        for warning in document.warnings:
            log.appendPlainText(f"  {warning}")
        for error in document.errors:
            log.appendPlainText(f"  {error}")


def section(title: str, layout: QLayout) -> QGroupBox:
    group = QGroupBox(title)
    group.setLayout(layout)
    return group


def widget_section(title: str, widget: QWidget) -> QGroupBox:
    layout = QVBoxLayout()
    layout.addWidget(widget)
    return section(title, layout)


def select_input_files(parent: QWidget, title: str) -> list[Path]:
    suffixes = " ".join(f"*{suffix}" for suffix in sorted(SUPPORTED_INPUT_SUFFIXES))
    files, _ = QFileDialog.getOpenFileNames(
        parent,
        title,
        str(Path.home()),
        f"Documents and images ({suffixes})",
    )
    return [Path(file).resolve() for file in files]


def select_output_folder(
    parent: QWidget, title: str, current_folder: str
) -> Path | None:
    folder = QFileDialog.getExistingDirectory(parent, title, current_folder)
    if folder:
        return Path(folder).resolve()
    return None
