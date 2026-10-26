from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from paddlepdf.gui_layout_types import (
    DocumentWidgets,
    HeaderWidgets,
    LayoutActions,
    LayoutWidgets,
    OutputWidgets,
    RunWidgets,
    SettingsWidgets,
)
from paddlepdf.gui_support import combo_box, quality_profile_box
from paddlepdf.i18n import UiLanguage
from paddlepdf.models import DeviceChoice, OutputFormat


def build_main_layout(actions: LayoutActions) -> LayoutWidgets:
    root = QWidget()
    layout = QVBoxLayout(root)
    layout.setContentsMargins(14, 12, 14, 12)
    layout.setSpacing(8)

    header = _build_header(actions)
    documents = _build_documents(actions)
    output = _build_output(actions)
    settings = _build_settings()
    run = _build_run(actions)
    log = _build_log()
    activity_label = _label("", "SectionTitle")

    layout.addLayout(header.layout)
    layout.addWidget(_divider())
    layout.addLayout(documents.header)
    layout.addWidget(documents.file_list)
    layout.addLayout(output.row)
    layout.addLayout(settings.grid)
    layout.addWidget(_divider())
    layout.addLayout(run.row)
    layout.addWidget(activity_label)
    layout.addWidget(log)
    layout.addStretch(1)

    return LayoutWidgets(
        root=root,
        file_list=documents.file_list,
        language_box=header.language_box,
        language_label=header.language_label,
        documents_label=documents.label,
        select_files_button=documents.select_files_button,
        output_folder=output.output_folder,
        output_label=output.label,
        select_output_button=output.select_output_button,
        orientation_box=settings.orientation_box,
        unwarp_box=settings.unwarp_box,
        layout_box=settings.layout_box,
        format_box=settings.format_box,
        profile_box=settings.profile_box,
        device_box=settings.device_box,
        format_label=settings.format_label,
        profile_label=settings.profile_label,
        device_label=settings.device_label,
        knobs_label=settings.knobs_label,
        progress_bar=run.progress_bar,
        status_label=run.status_label,
        convert_button=run.convert_button,
        open_folder_button=run.open_folder_button,
        activity_label=activity_label,
        log=log,
    )


def _build_header(actions: LayoutActions) -> HeaderWidgets:
    layout = QHBoxLayout()
    title_label = QLabel("PaddleOCR-GUI")
    title_label.setObjectName("AppTitle")
    language_label = QLabel()
    language_label.setObjectName("InlineLabel")
    language_box = combo_box(UiLanguage, actions.initial_language)
    language_box.currentTextChanged.connect(actions.apply_language)
    language_box.setFixedWidth(128)
    layout.addWidget(title_label)
    layout.addStretch(1)
    layout.addWidget(language_label)
    layout.addWidget(language_box)
    return HeaderWidgets(layout, language_box, language_label)


def _build_documents(actions: LayoutActions) -> DocumentWidgets:
    header = QHBoxLayout()
    header.setSpacing(8)
    label = _label("", "SectionTitle")
    select_files_button = QPushButton()
    select_files_button.clicked.connect(actions.select_files)
    header.addWidget(label)
    header.addStretch(1)
    header.addWidget(select_files_button)

    file_list = QListWidget()
    file_list.setObjectName("DocumentQueue")
    file_list.setFixedHeight(52)
    file_list.addItem("")
    return DocumentWidgets(header, label, file_list, select_files_button)


def _build_output(actions: LayoutActions) -> OutputWidgets:
    output_folder = QLineEdit(str(actions.output_dir))
    label = _label("", "InlineLabel")
    select_output_button = QPushButton()
    select_output_button.clicked.connect(actions.select_output_folder)
    row = QHBoxLayout()
    row.setSpacing(8)
    row.addWidget(label)
    row.addWidget(output_folder)
    row.addWidget(select_output_button)
    return OutputWidgets(row, label, output_folder, select_output_button)


def _build_settings() -> SettingsWidgets:
    orientation_box = QCheckBox()
    unwarp_box = QCheckBox()
    layout_box = QCheckBox()
    layout_box.setChecked(True)
    format_box = combo_box(OutputFormat, OutputFormat.MARKDOWN)
    format_box.setFixedWidth(104)
    profile_box = quality_profile_box(orientation_box, unwarp_box, layout_box)
    profile_box.setFixedWidth(132)
    device_box = combo_box(DeviceChoice, DeviceChoice.GPU)
    device_box.setFixedWidth(92)
    format_label = QLabel()
    profile_label = QLabel()
    device_label = QLabel()
    knobs_label = QLabel()

    grid = QGridLayout()
    grid.setContentsMargins(0, 0, 0, 0)
    grid.setHorizontalSpacing(8)
    grid.setVerticalSpacing(6)
    grid.addWidget(format_label, 0, 0)
    grid.addWidget(format_box, 0, 1)
    grid.addWidget(profile_label, 0, 2)
    grid.addWidget(profile_box, 0, 3)
    grid.addWidget(device_label, 0, 4)
    grid.addWidget(device_box, 0, 5)
    grid.addWidget(knobs_label, 1, 0)
    grid.addWidget(orientation_box, 1, 1)
    grid.addWidget(unwarp_box, 1, 2)
    grid.addWidget(layout_box, 1, 3, 1, 3)
    return SettingsWidgets(
        grid=grid,
        orientation_box=orientation_box,
        unwarp_box=unwarp_box,
        layout_box=layout_box,
        format_box=format_box,
        profile_box=profile_box,
        device_box=device_box,
        format_label=format_label,
        profile_label=profile_label,
        device_label=device_label,
        knobs_label=knobs_label,
    )


def _build_run(actions: LayoutActions) -> RunWidgets:
    progress_bar = QProgressBar()
    progress_bar.setMinimum(0)
    status_label = QLabel()
    status_label.setObjectName("StatusLabel")
    convert_button = QPushButton()
    convert_button.setObjectName("PrimaryButton")
    convert_button.clicked.connect(actions.start_conversion)
    open_folder_button = QPushButton()
    open_folder_button.clicked.connect(actions.open_output_folder)
    open_folder_button.setEnabled(False)

    row = QHBoxLayout()
    row.setSpacing(8)
    row.addWidget(progress_bar, 1)
    row.addWidget(status_label)
    row.addWidget(convert_button)
    row.addWidget(open_folder_button)
    return RunWidgets(
        row, progress_bar, status_label, convert_button, open_folder_button
    )


def _build_log() -> QPlainTextEdit:
    log = QPlainTextEdit()
    log.setReadOnly(True)
    log.setFixedHeight(56)
    return log


def _label(label_text: str, object_name: str) -> QLabel:
    label = QLabel(label_text)
    label.setObjectName(object_name)
    return label


def _divider() -> QFrame:
    divider = QFrame()
    divider.setObjectName("Divider")
    divider.setFrameShape(QFrame.Shape.HLine)
    return divider
