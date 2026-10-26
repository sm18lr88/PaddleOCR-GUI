"""Size reduction: JPEG recompression of plain raster images plus object streams."""

import shutil
from io import BytesIO
from typing import Annotated, Final

import pikepdf
from PIL import Image
from pydantic import Field, JsonValue

from paddlepdf.pdftools.common import input_path, open_pdf, output_path
from paddlepdf.pdftools.contract import PdfToolError, ToolOutcome
from paddlepdf.pdftools.structure_ops._params import (
    InputFile,
    OutputFile,
    Password,
    encryption_warnings,
)

PRESETS: Final = {
    "low": (1024, 40),
    "screen": (1024, 40),
    "medium": (1600, 60),
    "ebook": (1600, 60),
    "high": (2400, 80),
    "prepress": (2400, 80),
}
DEFAULT_MAX_DIMENSION: Final = 1600
RECOMPRESSIBLE_COLORSPACES: Final = frozenset({"/DeviceRGB", "/DeviceGray"})
RECOMPRESSIBLE_FILTERS: Final = ((), ("/FlateDecode",), ("/DCTDecode",))
UNSAFE_IMAGE_KEYS: Final = ("/SMask", "/Mask", "/Decode", "/ImageMask")
BITS_PER_COMPONENT: Final = 8
MAX_JPEG_QUALITY: Final = 100


def parse_quality(quality: str) -> tuple[int, int]:
    """Return ``(max_dimension, jpeg_quality)`` for a preset name or 1-100 integer."""
    cleaned = quality.strip().lower()
    if cleaned in PRESETS:
        return PRESETS[cleaned]
    if cleaned.isdigit() and 1 <= int(cleaned) <= MAX_JPEG_QUALITY:
        return DEFAULT_MAX_DIMENSION, int(cleaned)
    msg = (
        f"Invalid quality {quality!r}; use low/medium/high "
        "(or screen/ebook/prepress) or an integer 1-100"
    )
    raise PdfToolError(msg)


def _filters(image: pikepdf.Stream) -> tuple[str, ...]:
    value = image.get("/Filter")
    if value is None:
        return ()
    if isinstance(value, pikepdf.Array):
        return tuple(str(item) for item in value)
    return (str(value),)


def _recompressible(image: pikepdf.Stream) -> bool:
    return (
        not any(key in image for key in UNSAFE_IMAGE_KEYS)
        and int(image.get("/BitsPerComponent", 0)) == BITS_PER_COMPONENT
        and str(image.get("/ColorSpace", "")) in RECOMPRESSIBLE_COLORSPACES
        and _filters(image) in RECOMPRESSIBLE_FILTERS
    )


def _recompress(image: pikepdf.Stream, max_dimension: int, jpeg_quality: int) -> bool:
    picture = pikepdf.PdfImage(image).as_pil_image()
    if max(picture.size) > max_dimension:
        picture.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)
    buffer = BytesIO()
    picture.save(buffer, format="JPEG", quality=jpeg_quality, optimize=True)
    encoded = buffer.getvalue()
    if len(encoded) >= len(image.read_raw_bytes()):
        return False
    image.write(encoded, filter=pikepdf.Name.DCTDecode)
    if "/DecodeParms" in image:
        del image.DecodeParms
    image.Width, image.Height = picture.size
    return True


def _image_streams(pdf: pikepdf.Pdf) -> list[pikepdf.Stream]:
    return [
        candidate
        for candidate in pdf.objects
        if isinstance(candidate, pikepdf.Stream)
        and candidate.get("/Subtype") == pikepdf.Name.Image
    ]


def pdf_compress(
    input_file: InputFile,
    output_file: OutputFile,
    quality: Annotated[
        str,
        Field(
            description=(
                "Preset low/medium/high (aliases screen/ebook/prepress; caps images "
                "at 1024/1600/2400 px with JPEG quality 40/60/80) or JPEG quality "
                "1-100 with a 1600 px cap."
            )
        ),
    ] = "medium",
    password: Password = None,
) -> ToolOutcome:
    max_dimension, jpeg_quality = parse_quality(quality)
    source = input_path(input_file)
    target = output_path(output_file, source)
    skipped = 0
    recompressed = 0
    with open_pdf(source, password) as pdf:
        warnings = list(encryption_warnings(pdf))
        images = _image_streams(pdf)
        for image in images:
            if not _recompressible(image):
                skipped += 1
                continue
            try:
                recompressed += _recompress(image, max_dimension, jpeg_quality)
            except (pikepdf.PikepdfError, NotImplementedError, OSError):
                skipped += 1
        pdf.save(
            target,
            compress_streams=True,
            recompress_flate=True,
            object_stream_mode=pikepdf.ObjectStreamMode["generate"],
        )
    original_size = source.stat().st_size
    compressed_size = target.stat().st_size
    kept_original = compressed_size >= original_size
    if kept_original:
        shutil.copyfile(source, target)
        warnings = ["Compression did not shrink the file; the original was copied."]
    data: dict[str, JsonValue] = {
        "original_size": original_size,
        "output_size": target.stat().st_size,
        "kept_original": kept_original,
        "images_found": len(images),
        "images_recompressed": recompressed,
        "images_skipped": skipped,
        "max_dimension": max_dimension,
        "jpeg_quality": jpeg_quality,
    }
    return ToolOutcome(output_files=(str(target),), data=data, warnings=tuple(warnings))
