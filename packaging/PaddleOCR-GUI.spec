# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs


project_root = Path(SPECPATH).parent
entry_script = project_root / "packaging" / "paddleocr_gui_entry.py"
runtime_hook = project_root / "packaging" / "pyinstaller_runtime_hook.py"


def collect_package_files(package_name):
    try:
        return collect_data_files(package_name), collect_dynamic_libs(package_name)
    except Exception:
        return [], []


datas = []
binaries = []
hiddenimports = [
    "paddleocr",
    "paddleocr._pipelines.paddleocr_vl",
    "paddlex",
    "paddlex.inference.models.common.genai",
    "paddlex.inference.models.doc_vlm.predictor",
    "paddlex.inference.pipelines.paddleocr_vl.pipeline",
    "paddle",
    "openai",
    "httpx",
]

for package in (
    "paddleocr",
    "paddlex",
    "paddle",
    "nvidia",
    "cv2",
    "PIL",
    "openai",
    "httpx",
):
    package_datas, package_binaries = collect_package_files(package)
    datas += package_datas
    binaries += package_binaries

a = Analysis(
    [str(entry_script)],
    pathex=[str(project_root / "src")],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[str(runtime_hook)],
    excludes=["tkinter", "pytest"],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="PaddleOCR-GUI",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="PaddleOCR-GUI",
)
