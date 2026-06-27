from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from paddlepdf.models import ArtifactFormat, ConversionOptions, PlannedDocument
from paddlepdf.planning import artifact_formats, expected_text_file

if TYPE_CHECKING:
    from paddleocr import PaddleOCRVLResult


def save_vl_result(
    result: PaddleOCRVLResult,
    output_dir: Path,
    formats: tuple[ArtifactFormat, ...],
) -> None:
    if ArtifactFormat.JSON in formats:
        result.save_to_json(save_path=output_dir)
    if ArtifactFormat.MARKDOWN in formats or ArtifactFormat.TEXT in formats:
        result.save_to_markdown(save_path=output_dir)


def collect_output_files(
    document: PlannedDocument,
    options: ConversionOptions,
    before: frozenset[Path],
) -> tuple[Path, ...]:
    created = existing_files(document.output_dir) - before
    requested = artifact_formats(options.output_format)
    text_files = materialize_text_outputs(document, created, requested)
    kept = [path for path in created if matches_requested_format(path, requested)]
    return tuple(sorted((*kept, *text_files), key=lambda path: path.as_posix()))


def existing_files(output_dir: Path) -> frozenset[Path]:
    if not output_dir.exists():
        return frozenset()
    return frozenset(path for path in output_dir.rglob("*") if path.is_file())


def materialize_text_outputs(
    document: PlannedDocument,
    created: frozenset[Path],
    requested: tuple[ArtifactFormat, ...],
) -> tuple[Path, ...]:
    if ArtifactFormat.TEXT not in requested:
        return ()
    markdown_files = sorted(path for path in created if path.suffix.lower() == ".md")
    text_file = expected_text_file(document)
    text_file.write_text(
        "\n\n".join(path.read_text(encoding="utf-8") for path in markdown_files),
        encoding="utf-8",
    )
    if ArtifactFormat.MARKDOWN not in requested:
        for markdown_file in markdown_files:
            markdown_file.unlink(missing_ok=True)
    return (text_file,)


def matches_requested_format(
    path: Path,
    requested: tuple[ArtifactFormat, ...],
) -> bool:
    suffix = path.suffix.lower()
    return (
        (suffix == ".json" and ArtifactFormat.JSON in requested)
        or (suffix == ".md" and ArtifactFormat.MARKDOWN in requested)
        or (suffix == ".txt" and ArtifactFormat.TEXT in requested)
    )
