from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QThread
from PySide6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from paddlepdf.gui_support import (
    ConversionWorker,
    append_report_to_log,
    combo_box,
    open_output_folder,
    quality_profile_box,
    section,
    select_input_files,
    select_output_folder,
    set_running_controls,
    widget_section,
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
        self.resize(820, 640)
        self._build_ui()
        self._apply_language(self._language.value)

    def _build_ui(self) -> None:
        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)
        self.title_label = QLabel("PaddleOCR-GUI")
        self.title_label.setObjectName("AppTitle")
        self.subtitle_label = QLabel("Native Windows GPU-first document conversion")
        self.subtitle_label.setObjectName("AppSubtitle")
        self.file_list = QListWidget()
        self.file_list.setObjectName("DocumentQueue")
        self.file_list.addItem("No documents selected. Choose PDFs/images to start.")
        self.language_box = combo_box(UiLanguage, self._language)
        self.language_box.currentTextChanged.connect(self._apply_language)
        self.language_label = QLabel()
        language_row = QHBoxLayout()
        language_row.setSpacing(8)
        language_row.addWidget(self.language_label)
        language_row.addWidget(self.language_box)
        self.select_files_button = QPushButton()
        self.select_files_button.clicked.connect(self._select_files)
        self.output_folder = QLineEdit(str(self._latest_output_dir))
        self.select_output_button = QPushButton()
        self.select_output_button.clicked.connect(self._select_output_folder)
        output_row = QHBoxLayout()
        output_row.setSpacing(8)
        output_row.addWidget(self.output_folder)
        output_row.addWidget(self.select_output_button)
        self.orientation_box = QCheckBox()
        self.unwarp_box = QCheckBox()
        self.layout_box = QCheckBox()
        self.layout_box.setChecked(True)
        self.format_box = combo_box(OutputFormat, OutputFormat.MARKDOWN)
        self.profile_box = quality_profile_box(
            self.orientation_box, self.unwarp_box, self.layout_box
        )
        self.device_box = combo_box(DeviceChoice, DeviceChoice.GPU)
        self.format_label = QLabel()
        self.profile_label = QLabel()
        self.device_label = QLabel()
        self.knobs_label = QLabel()
        form = QFormLayout()
        form.setContentsMargins(0, 4, 0, 4)
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(8)
        form.addRow(self.format_label, self.format_box)
        form.addRow(self.profile_label, self.profile_box)
        form.addRow(self.device_label, self.device_box)
        form.addRow(self.knobs_label, self.orientation_box)
        form.addRow(QLabel(), self.unwarp_box)
        form.addRow(QLabel(), self.layout_box)
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.status_label = QLabel()
        self.status_label.setObjectName("StatusLabel")
        self.convert_button = QPushButton()
        self.convert_button.setObjectName("PrimaryButton")
        self.convert_button.clicked.connect(self._start_conversion)
        self.open_folder_button = QPushButton()
        self.open_folder_button.clicked.connect(
            lambda: open_output_folder(self._latest_output_dir)
        )
        self.open_folder_button.setEnabled(False)
        actions = QHBoxLayout()
        actions.setSpacing(8)
        actions.addStretch(1)
        actions.addWidget(self.convert_button)
        actions.addWidget(self.open_folder_button)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setFixedHeight(88)
        self.log.setPlaceholderText("Conversion status will appear here.")
        documents_layout = QVBoxLayout()
        documents_layout.setSpacing(8)
        documents_layout.addWidget(self.select_files_button)
        documents_layout.addWidget(self.file_list)
        output_layout = QVBoxLayout()
        output_layout.addLayout(output_row)
        run_layout = QVBoxLayout()
        run_layout.setSpacing(8)
        run_layout.addWidget(self.progress_bar)
        run_layout.addWidget(self.status_label)
        run_layout.addLayout(actions)
        layout.addWidget(self.title_label)
        layout.addWidget(self.subtitle_label)
        layout.addLayout(language_row)
        layout.addWidget(section("1. Documents", documents_layout))
        layout.addWidget(section("2. Output", output_layout))
        layout.addWidget(section("3. OCR settings", form))
        layout.addWidget(section("4. Run", run_layout))
        layout.addWidget(widget_section("Activity log", self.log))
        self.setCentralWidget(root)

    def _select_files(self) -> None:
        files = select_input_files(self, text(self._language, "select_pdf_files"))
        if not files:
            return
        self._input_files = files
        self.file_list.clear()
        for file in self._input_files:
            self.file_list.addItem(str(file))

    def _select_output_folder(self) -> None:
        title = text(self._language, "choose_output")
        current_folder = self.output_folder.text()
        folder = select_output_folder(self, title, current_folder)
        if folder is not None:
            self.output_folder.setText(str(folder))

    def _start_conversion(self) -> None:
        if not self._input_files:
            QMessageBox.warning(
                self,
                text(self._language, "missing_pdfs_title"),
                text(self._language, "missing_pdfs_body"),
            )
            return
        output_dir = Path(self.output_folder.text()).expanduser().resolve()
        request = ConversionRequest(
            input_files=tuple(self._input_files),
            output_dir=output_dir,
            options=ConversionOptions(
                output_format=OutputFormat(self.format_box.currentText()),
                profile=QualityProfile(self.profile_box.currentText()),
                device=DeviceChoice(self.device_box.currentText()),
                orientation_correction=self.orientation_box.isChecked(),
                document_unwarping=self.unwarp_box.isChecked(),
                preserve_layout=self.layout_box.isChecked(),
            ),
        )
        self._latest_output_dir = output_dir
        set_running_controls(
            self.convert_button,
            self.open_folder_button,
            self._latest_output_dir,
            running=True,
        )
        self.log.clear()
        self.progress_bar.setMaximum(len(self._input_files))
        self.progress_bar.setValue(0)
        self._thread = QThread(self)
        self._worker = ConversionWorker(request)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.finished.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        self.status_label.setText(text(self._language, "starting"))
        self._thread.start()

    def _on_progress(
        self, index: int, total: int, file_name: str, message: str
    ) -> None:
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(max(index - 1, 0))
        self.status_label.setText(f"{file_name}: {message}")
        self.log.appendPlainText(f"{index}/{total} {file_name}: {message}")

    def _on_finished(self, report: AgentRunReport) -> None:
        self.progress_bar.setValue(self.progress_bar.maximum())
        self.status_label.setText(
            f"{text(self._language, 'complete')}: {report.status.value}"
        )
        set_running_controls(
            self.convert_button,
            self.open_folder_button,
            self._latest_output_dir,
            running=False,
        )
        self.open_folder_button.setEnabled(True)
        append_report_to_log(self.log, report)
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
        self.language_label.setText(text(self._language, "language"))
        self.select_files_button.setText(text(self._language, "select_pdfs"))
        self.select_output_button.setText(text(self._language, "choose_output"))
        self.format_label.setText(text(self._language, "output_format"))
        self.profile_label.setText(text(self._language, "profile"))
        self.device_label.setText(text(self._language, "device"))
        self.knobs_label.setText(text(self._language, "ocr_knobs"))
        self.orientation_box.setText(text(self._language, "orientation"))
        self.unwarp_box.setText(text(self._language, "unwarp"))
        self.layout_box.setText(text(self._language, "preserve_layout"))
        self.convert_button.setText(text(self._language, "convert"))
        self.open_folder_button.setText(text(self._language, "open_folder"))
        if self.status_label.text() in {"", text(UiLanguage.ENGLISH, "ready")}:
            self.status_label.setText(text(self._language, "ready"))
