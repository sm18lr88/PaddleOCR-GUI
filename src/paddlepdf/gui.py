from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QThread
from PySide6.QtWidgets import QMainWindow, QMessageBox

from paddlepdf.gui_layout import build_main_layout
from paddlepdf.gui_layout_types import LayoutActions, LayoutWidgets
from paddlepdf.gui_support import (
    ConversionWorker,
    append_report_to_log,
    open_output_folder,
    select_input_files,
    select_output_folder,
    set_running_controls,
)
from paddlepdf.i18n import RTL_LANGUAGES, UiLanguage, detect_ui_language, text
from paddlepdf.models import (
    AgentRunReport,
    ConversionOptions,
    ConversionRequest,
    DeviceChoice,
    OutputFormat,
    QualityProfile,
)


class PaddlePdfWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self._input_files: list[Path] = []
        self._latest_output_dir = Path("output").resolve()
        self._language = detect_ui_language()
        self._thread: QThread | None = None
        self._worker: ConversionWorker | None = None
        self._layout: LayoutWidgets = build_main_layout(
            LayoutActions(
                initial_language=self._language,
                output_dir=self._latest_output_dir,
                apply_language=self._apply_language,
                select_files=self._select_files,
                select_output_folder=self._select_output_folder,
                start_conversion=self._start_conversion,
                open_output_folder=lambda: open_output_folder(self._latest_output_dir),
            )
        )
        self.resize(900, 560)
        self.setCentralWidget(self._layout.root)
        self._apply_language(self._language.value)

    def _select_files(self) -> None:
        files = select_input_files(self, text(self._language, "select_pdf_files"))
        if not files:
            return
        self._input_files = files
        self._layout.file_list.clear()
        for file in self._input_files:
            self._layout.file_list.addItem(str(file))

    def _select_output_folder(self) -> None:
        title = text(self._language, "choose_output")
        current_folder = self._layout.output_folder.text()
        folder = select_output_folder(self, title, current_folder)
        if folder is not None:
            self._layout.output_folder.setText(str(folder))

    def _start_conversion(self) -> None:
        if not self._input_files:
            QMessageBox.warning(
                self,
                text(self._language, "missing_pdfs_title"),
                text(self._language, "missing_pdfs_body"),
            )
            return
        ui = self._layout
        output_dir = Path(ui.output_folder.text()).expanduser().resolve()
        request = ConversionRequest(
            input_files=tuple(self._input_files),
            output_dir=output_dir,
            options=ConversionOptions(
                output_format=OutputFormat(ui.format_box.currentText()),
                profile=QualityProfile(ui.profile_box.currentText()),
                device=DeviceChoice(ui.device_box.currentText()),
                orientation_correction=ui.orientation_box.isChecked(),
                document_unwarping=ui.unwarp_box.isChecked(),
                preserve_layout=ui.layout_box.isChecked(),
            ),
        )
        self._latest_output_dir = output_dir
        set_running_controls(
            ui.convert_button,
            ui.open_folder_button,
            self._latest_output_dir,
            running=True,
        )
        ui.log.clear()
        ui.progress_bar.setMaximum(len(self._input_files))
        ui.progress_bar.setValue(0)
        self._thread = QThread(self)
        self._worker = ConversionWorker(request)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.finished.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        ui.status_label.setText(text(self._language, "starting"))
        self._thread.start()

    def _on_progress(
        self, index: int, total: int, file_name: str, message: str
    ) -> None:
        ui = self._layout
        ui.progress_bar.setMaximum(total)
        ui.progress_bar.setValue(max(index - 1, 0))
        ui.status_label.setText(f"{file_name}: {message}")
        ui.log.appendPlainText(f"{index}/{total} {file_name}: {message}")

    def _on_finished(self, report: AgentRunReport) -> None:
        ui = self._layout
        ui.progress_bar.setValue(ui.progress_bar.maximum())
        ui.status_label.setText(
            f"{text(self._language, 'complete')}: {report.status.value}"
        )
        set_running_controls(
            ui.convert_button,
            ui.open_folder_button,
            self._latest_output_dir,
            running=False,
        )
        ui.open_folder_button.setEnabled(True)
        append_report_to_log(ui.log, report)
        if report.output_files:
            answer = QMessageBox.question(
                self,
                text(self._language, "conversion_complete_title"),
                text(self._language, "open_output_question"),
            )
            if answer == QMessageBox.StandardButton.Yes:
                open_output_folder(self._latest_output_dir)
        self._thread = None
        self._worker = None

    def _apply_language(self, value: str) -> None:
        self._language = UiLanguage(value)
        self.setLayoutDirection(
            Qt.LayoutDirection.RightToLeft
            if self._language in RTL_LANGUAGES
            else Qt.LayoutDirection.LeftToRight
        )
        self.setWindowTitle(text(self._language, "window_title"))
        ui = self._layout
        ui.language_label.setText(text(self._language, "language"))
        ui.documents_label.setText(text(self._language, "documents"))
        ui.select_files_button.setText(text(self._language, "select_pdfs"))
        if not self._input_files and ui.file_list.count() > 0:
            ui.file_list.item(0).setText(text(self._language, "document_empty"))
        ui.output_label.setText(text(self._language, "output_folder"))
        ui.select_output_button.setText(text(self._language, "choose_output"))
        ui.format_label.setText(text(self._language, "output_format"))
        ui.profile_label.setText(text(self._language, "profile"))
        ui.device_label.setText(text(self._language, "device"))
        ui.knobs_label.setText(text(self._language, "ocr_knobs"))
        ui.orientation_box.setText(text(self._language, "orientation"))
        ui.unwarp_box.setText(text(self._language, "unwarp"))
        ui.layout_box.setText(text(self._language, "preserve_layout"))
        ui.convert_button.setText(text(self._language, "convert"))
        ui.open_folder_button.setText(text(self._language, "open_folder"))
        ui.activity_label.setText(text(self._language, "activity"))
        ui.log.setPlaceholderText(text(self._language, "log_placeholder"))
        ready_texts = {text(language, "ready") for language in UiLanguage}
        if ui.status_label.text() in {"", *ready_texts}:
            ui.status_label.setText(text(self._language, "ready"))
