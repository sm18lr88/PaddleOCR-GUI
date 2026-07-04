from __future__ import annotations

import re
from pathlib import Path

from paddlepdf.models import ArtifactFormat, OutputFormat, PlannedDocument

SAFE_PART_PATTERN = re.compile(r"[^A-Za-z0-9._-]+")
SUPPORTED_INPUT_SUFFIXES = frozenset(
    {".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"}
)


def artifact_formats(output_format: OutputFormat) -> tuple[ArtifactFormat, ...]:
    match output_format:
        case OutputFormat.MARKDOWN:
            return (ArtifactFormat.MARKDOWN,)
        case OutputFormat.JSON:
            return (ArtifactFormat.JSON,)
        case OutputFormat.TEXT:
            return (ArtifactFormat.TEXT,)
        case OutputFormat.ALL:
            return (ArtifactFormat.MARKDOWN, ArtifactFormat.JSON, ArtifactFormat.TEXT)


def safe_document_stem(path: Path) -> str:
    cleaned = SAFE_PART_PATTERN.sub("-", path.stem.strip()).strip(".-_")
    if cleaned:
        return cleaned[:96]
    return "document"


def plan_documents(
    input_files: tuple[Path, ...], output_dir: Path
) -> tuple[PlannedDocument, ...]:
    counts: dict[str, int] = {}
    planned: list[PlannedDocument] = []
    for input_file in input_files:
        base_stem = safe_document_stem(input_file)
        next_count = counts.get(base_stem, 0) + 1
        counts[base_stem] = next_count
        output_stem = base_stem if next_count == 1 else f"{base_stem}-{next_count}"
        planned.append(
            PlannedDocument(
                input_file=input_file,
                output_dir=output_dir / output_stem,
                safe_stem=output_stem,
            ),
        )
    return tuple(planned)


def expected_text_file(document: PlannedDocument) -> Path:
    return document.output_dir / f"{document.safe_stem}.txt"
