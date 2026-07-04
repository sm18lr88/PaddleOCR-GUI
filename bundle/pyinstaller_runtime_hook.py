from __future__ import annotations

import os
import sys
from pathlib import Path


def _bundle_root() -> Path:
    frozen_root = getattr(sys, "_MEIPASS", None)
    if isinstance(frozen_root, str):
        return Path(frozen_root)
    return Path(sys.executable).resolve().parent


def _dll_roots(root: Path) -> tuple[Path, ...]:
    return (
        root,
        root / "_internal",
        root / "paddle" / "libs",
        root / "_internal" / "paddle" / "libs",
        root / "nvidia",
        root / "_internal" / "nvidia",
    )


def _add_dll_directory(path: Path) -> None:
    if path.exists():
        os.add_dll_directory(str(path))


if sys.platform == "win32":
    for dll_root in _dll_roots(_bundle_root()):
        _add_dll_directory(dll_root)
        if dll_root.name == "nvidia" and dll_root.exists():
            for child in dll_root.rglob("bin"):
                _add_dll_directory(child)
