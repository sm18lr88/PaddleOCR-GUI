"""Preset workflow catalog ported from PaperPilot, mapped to the ported tool names."""

from dataclasses import dataclass

from pydantic import JsonValue


@dataclass(frozen=True, slots=True)
class PresetStep:
    tool: str
    label: str
    params: dict[str, JsonValue]


@dataclass(frozen=True, slots=True)
class Preset:
    id: str
    name: str
    description: str
    steps: tuple[PresetStep, ...]
    required_step_params: dict[str, str]


PRESETS: tuple[Preset, ...] = (
    Preset(
        id="preset-legal-discovery",
        name="Legal Discovery Prep",
        description=(
            "Applies Bates numbering, confidential watermark, and web linearization."
        ),
        steps=(
            PresetStep(
                "pdf_bates",
                "Bates Numbering",
                {"prefix": "CONFIDENTIAL-", "start_number": 1},
            ),
            PresetStep("pdf_watermark", "Watermark", {"text": "CONFIDENTIAL"}),
            PresetStep("pdf_linearize", "Linearize", {}),
        ),
        required_step_params={},
    ),
    Preset(
        id="preset-clean-scan",
        name="Clean & Optimize Scan",
        description="Removes blank pages, adds page numbers, and compresses file size.",
        steps=(
            PresetStep("pdf_remove_blank", "Remove Blank Pages", {}),
            PresetStep(
                "pdf_page_numbers", "Page Numbers", {"position": "bottom-right"}
            ),
            PresetStep("pdf_compress", "Compress", {"quality": "75"}),
        ),
        required_step_params={},
    ),
    Preset(
        id="preset-redact-protect",
        name="Redact & Secure Document",
        description=(
            "Redacts sensitive content, flattens annotations, and encrypts PDF."
        ),
        steps=(
            PresetStep("pdf_redact", "Redact Content", {}),
            PresetStep("pdf_flatten", "Flatten Annotations", {}),
            PresetStep("pdf_encrypt", "Encrypt", {}),
        ),
        required_step_params={
            "pdf_redact": "search_text and/or regions",
            "pdf_encrypt": "user_password",
        },
    ),
)


def find_preset(identifier: str) -> Preset | None:
    wanted = identifier.strip()
    return next(
        (
            preset
            for preset in PRESETS
            if wanted in (preset.id, preset.id.removeprefix("preset-"))
            or f"preset-{wanted}" == preset.id
        ),
        None,
    )
