from __future__ import annotations

import os
from pathlib import Path, PureWindowsPath
from typing import Final
from urllib.parse import unquote, urlparse

DRIVE_PATH_PREFIX_LENGTH: Final = 3
WRAPPING_QUOTE_MIN_LENGTH: Final = 2


def user_path(value: str | Path) -> Path:
    raw_path = value if isinstance(value, Path) else Path(_clean_path_text(value))
    return raw_path.expanduser().resolve()


def user_paths(values: tuple[str | Path, ...]) -> tuple[Path, ...]:
    return tuple(user_path(value) for value in values)


def _clean_path_text(value: str) -> str:
    cleaned = _strip_wrapping_quotes(value.strip())
    parsed = urlparse(cleaned)
    if parsed.scheme == "file":
        cleaned = _file_uri_path(parsed.netloc, parsed.path)
    if os.name == "nt":
        cleaned = _windows_compat_path(cleaned)
    return cleaned


def _strip_wrapping_quotes(value: str) -> str:
    cleaned = value
    while (
        len(cleaned) >= WRAPPING_QUOTE_MIN_LENGTH
        and cleaned[0] == cleaned[-1]
        and cleaned[0] in {'"', "'"}
    ):
        cleaned = cleaned[1:-1].strip()
    return cleaned


def _file_uri_path(netloc: str, path: str) -> str:
    decoded_path = unquote(path)
    if os.name == "nt" and _has_leading_windows_drive(decoded_path):
        decoded_path = decoded_path[1:]
    if netloc and os.name == "nt":
        return str(PureWindowsPath(f"//{netloc}{decoded_path}"))
    return decoded_path


def _windows_compat_path(value: str) -> str:
    cleaned = _collapse_escaped_backslashes(value)
    drive_path = _drive_path_from_posix_mount(cleaned)
    if drive_path is not None:
        return drive_path
    return cleaned


def _collapse_escaped_backslashes(value: str) -> str:
    if value.startswith("\\\\"):
        return value
    cleaned = value
    while "\\\\" in cleaned:
        cleaned = cleaned.replace("\\\\", "\\")
    return cleaned


def _drive_path_from_posix_mount(value: str) -> str | None:
    normalized = value.replace("\\", "/")
    parts = normalized.split("/")
    if len(parts) < DRIVE_PATH_PREFIX_LENGTH:
        return None
    if parts[0] == "" and parts[1] == "mnt" and _is_drive_letter(parts[2]):
        return _windows_drive_path(parts[2], parts[3:])
    if parts[0] == "" and _is_drive_letter(parts[1]):
        return _windows_drive_path(parts[1], parts[2:])
    return None


def _windows_drive_path(drive: str, parts: list[str]) -> str:
    return str(PureWindowsPath(f"{drive.upper()}:/", *parts))


def _has_leading_windows_drive(path: str) -> bool:
    return (
        len(path) >= DRIVE_PATH_PREFIX_LENGTH
        and path[0] == "/"
        and _is_drive_letter(path[1])
        and path[2] == ":"
    )


def _is_drive_letter(value: str) -> bool:
    return len(value) == 1 and value.isascii() and value.isalpha()
