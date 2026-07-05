# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

from PyInstaller.utils.hooks import (
    collect_data_files,
    collect_dynamic_libs,
    collect_submodules,
    copy_metadata,
)


project_root = Path(SPECPATH).parent
entry_script = project_root / "bundle" / "paddleocr_gui_entry.py"
cli_entry_script = project_root / "bundle" / "paddleocr_cli_entry.py"
runtime_hook = project_root / "bundle" / "pyinstaller_runtime_hook.py"


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
hiddenimports += collect_submodules("paddlex.inference.models.doc_vlm.processors")
excludes = [
    "future.backports.email.feedparser",
    "future.backports.email.utils",
    "future.backports.http.client",
    "future.backports.http.cookiejar",
    "future.backports.urllib.parse",
    "modelscope.models.cv.anydoor",
    "modelscope.models.cv.anydoor.ldm.models.diffusion.ddpm",
    "modelscope.models.nlp.chatglm",
    "modelscope.models.nlp.chatglm.text_generation",
    "pytest",
    "tkinter",
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
    package_datas = collect_data_files(package)
    package_binaries = collect_dynamic_libs(package)
    datas += package_datas
    binaries += package_binaries

for distribution in (
    "beautifulsoup4",
    "einops",
    "ftfy",
    "httpx",
    "huggingface-hub",
    "imagesize",
    "Jinja2",
    "latex2mathml",
    "lxml",
    "modelscope",
    "opencv-contrib-python",
    "openai",
    "openpyxl",
    "paddleocr",
    "paddlepaddle-gpu",
    "paddlepdf",
    "paddlex",
    "premailer",
    "pyclipper",
    "pydantic-settings",
    "pypdfium2",
    "python-bidi",
    "regex",
    "safetensors",
    "scikit-learn",
    "scipy",
    "sentencepiece",
    "shapely",
    "tiktoken",
    "tokenizers",
):
    datas += copy_metadata(distribution)

gui_analysis = Analysis(
    [str(entry_script)],
    pathex=[str(project_root / "src")],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[str(runtime_hook)],
    excludes=excludes,
    noarchive=False,
    optimize=0,
)
cli_analysis = Analysis(
    [str(cli_entry_script)],
    pathex=[str(project_root / "src")],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[str(runtime_hook)],
    excludes=excludes,
    noarchive=False,
    optimize=0,
)
gui_pyz = PYZ(gui_analysis.pure)
cli_pyz = PYZ(cli_analysis.pure)

exe = EXE(
    gui_pyz,
    gui_analysis.dependencies,
    gui_analysis.scripts,
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

cli_exe = EXE(
    cli_pyz,
    cli_analysis.dependencies,
    cli_analysis.scripts,
    [],
    exclude_binaries=True,
    name="PaddleOCR-GUI-CLI",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
)

coll = COLLECT(
    exe,
    cli_exe,
    gui_analysis.binaries,
    gui_analysis.datas,
    cli_analysis.binaries,
    cli_analysis.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="PaddleOCR-GUI",
)
