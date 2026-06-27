from __future__ import annotations

import os
import sys
import sysconfig
from pathlib import Path


def add_windows_cuda_dll_directories() -> None:
    if sys.platform != "win32":
        return
    site_packages = Path(sysconfig.get_paths()["purelib"])
    nvidia_root = site_packages / "nvidia"
    if not nvidia_root.exists():
        return
    for dll_dir in nvidia_root.glob("*/bin"):
        if dll_dir.is_dir():
            os.add_dll_directory(str(dll_dir))
