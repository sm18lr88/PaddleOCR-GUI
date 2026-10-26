"""Image decoding and page placement shared by images_to_pdf, comics, and JSON."""

from dataclasses import dataclass
from io import BytesIO
from typing import Final, Literal, cast

from PIL import Image, ImageOps, UnidentifiedImageError
from reportlab.lib.pagesizes import A3, A4, A5, legal, letter
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen.canvas import Canvas

from paddlepdf.pdftools.contract import PdfToolError
from paddlepdf.pdftools.create.styles import PageSize

IMAGE_SUFFIXES: Final = (
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".bmp",
    ".gif",
    ".tif",
    ".tiff",
)
PAGE_SIZES: Final[dict[PageSize, tuple[float, float]]] = {
    PageSize.A3: A3,
    PageSize.A4: A4,
    PageSize.A5: A5,
    PageSize.LETTER: letter,
    PageSize.LEGAL: legal,
}
_EXIF_ORIENTATION: Final = 0x0112
_JPEG_PASSTHROUGH_MODES: Final = frozenset({"RGB", "L", "CMYK"})

type Fit = Literal["contain", "shrink", "stretch"]
type ImageOrientation = Literal["auto", "portrait", "landscape"]


@dataclass(frozen=True, slots=True)
class PreparedImage:
    reader: ImageReader
    width: int
    height: int


def _flatten(image: Image.Image) -> Image.Image:
    if image.mode in {"RGBA", "LA"} or "transparency" in image.info:
        rgba = image.convert("RGBA")
        canvas = Image.new("RGB", rgba.size, "white")
        canvas.paste(rgba, mask=rgba.getchannel("A"))
        return canvas
    return image.convert("L" if image.mode in {"1", "L"} else "RGB")


def prepare_image(data: bytes, label: str) -> PreparedImage:
    """Decode the first frame, honor EXIF orientation, and keep JPEG bytes when safe."""
    try:
        with Image.open(BytesIO(data)) as opened:
            opened.load()
            orientation = cast("int", opened.getexif().get(_EXIF_ORIENTATION, 1))
            if (
                opened.format == "JPEG"
                and orientation == 1
                and opened.mode in _JPEG_PASSTHROUGH_MODES
            ):
                return PreparedImage(ImageReader(BytesIO(data)), *opened.size)
            upright = _flatten(ImageOps.exif_transpose(opened))
    except (UnidentifiedImageError, OSError, SyntaxError) as error:
        msg = f"Cannot decode image {label}: {error}"
        raise PdfToolError(msg) from error
    return PreparedImage(ImageReader(upright), *upright.size)


def page_dimensions(
    image: PreparedImage,
    page_size: PageSize | None,
    orientation: ImageOrientation,
    margin: float,
) -> tuple[float, float]:
    if page_size is None:
        return image.width + 2 * margin, image.height + 2 * margin
    short, long = sorted(PAGE_SIZES[page_size])
    landscape = (
        image.width > image.height
        if orientation == "auto"
        else orientation == "landscape"
    )
    return (long, short) if landscape else (short, long)


def draw_image_page(
    canvas: Canvas,
    image: PreparedImage,
    page_size: PageSize | None = None,
    orientation: ImageOrientation = "auto",
    fit: Fit = "contain",
    margin_mm: float = 0,
) -> None:
    """Add a page showing ``image``; ``page_size=None`` sizes the page to it."""
    margin = margin_mm * mm
    page_width, page_height = page_dimensions(image, page_size, orientation, margin)
    box_width, box_height = page_width - 2 * margin, page_height - 2 * margin
    if box_width <= 0 or box_height <= 0:
        msg = f"Margin {margin_mm} mm leaves no room on the page"
        raise PdfToolError(msg)
    if fit == "stretch":
        width, height = box_width, box_height
    else:
        scale = min(box_width / image.width, box_height / image.height)
        if fit == "shrink":
            scale = min(scale, 1.0)
        width, height = image.width * scale, image.height * scale
    canvas.setPageSize((page_width, page_height))
    canvas.drawImage(
        image.reader,
        margin + (box_width - width) / 2,
        margin + (box_height - height) / 2,
        width,
        height,
    )
    canvas.showPage()
