"""Document-type classification: topic keywords plus digital/scanned detection."""

from typing import Annotated, Final, SupportsFloat, cast

import pikepdf
from pydantic import Field, JsonValue

from paddlepdf.pdftools.common import input_path, open_pdf
from paddlepdf.pdftools.contract import ToolOutcome
from paddlepdf.pdftools.pdfium import page_texts

CATEGORIES: Final = (
    ("Invoice", ("invoice", "total", "tax", "due date", "balance")),
    ("Contract", ("agreement", "hereby", "party of the first part", "signatures")),
    ("Research Paper", ("abstract", "references", "methodology")),
    ("Form", ("application", "date of birth", "signature")),
)
KEYWORD_PAGES: Final = 3
MIN_TEXT_CHARS: Final = 25
IMAGE_PAGE_COVERAGE: Final = 0.5


def pdf_classify_type(
    input_file: Annotated[str, Field(description="Input PDF path.")],
    password: Annotated[str | None, Field(description="Password if encrypted.")] = None,
) -> ToolOutcome:
    path = input_path(input_file)
    texts = page_texts(path, password)
    category, confidence = _keyword_category(" ".join(texts[:KEYWORD_PAGES]).lower())
    with open_pdf(path, password) as pdf:
        analysed = [
            _page_facts(number, page, text)
            for number, (page, text) in enumerate(
                zip(pdf.pages, texts, strict=False), 1
            )
        ]
    pages: list[JsonValue] = [facts for _, facts in analysed]
    data: dict[str, JsonValue] = {
        "type": category,
        "confidence": confidence,
        "scan_kind": _document_kind({kind for kind, _ in analysed}),
        "pages": pages,
    }
    return ToolOutcome(data=data)


def _keyword_category(text: str) -> tuple[str, float]:
    best, best_score, total = "Unknown", 0, 0
    for category, keywords in CATEGORIES:
        score = sum(text.count(keyword) for keyword in keywords)
        total += score
        if score > best_score:
            best, best_score = category, score
    return best, (best_score / total if total else 0.0)


def _document_kind(kinds: set[str]) -> str:
    if "scanned" in kinds:
        return "mixed" if "digital" in kinds else "scanned"
    return "digital" if "digital" in kinds else "blank"


def _page_facts(
    number: int, page: pikepdf.Page, text: str
) -> tuple[str, dict[str, JsonValue]]:
    chars = len("".join(text.split()))
    coverage = _image_coverage(page)
    if coverage >= IMAGE_PAGE_COVERAGE:
        kind = "scanned"
    elif chars >= MIN_TEXT_CHARS:
        kind = "digital"
    else:
        kind = "blank" if coverage == 0 else "digital"
    facts: dict[str, JsonValue] = {
        "page": number,
        "text_chars": chars,
        "image_coverage": round(coverage, 3),
        "kind": kind,
    }
    return kind, facts


def _image_coverage(page: pikepdf.Page) -> float:
    """Fraction of the page covered by placed images (overlaps summed, capped at 1)."""
    left, bottom, right, top = (float(value) for value in page.mediabox)
    area = abs((right - left) * (top - bottom))
    if area == 0:
        return 0.0
    xobjects = page.resources.get("/XObject")
    scale = 1.0
    stack: list[float] = []
    covered = 0.0
    for item in pikepdf.parse_content_stream(page):
        if isinstance(item, pikepdf.ContentStreamInlineImage):
            covered += abs(scale)
            continue
        operator = str(item.operator)
        if operator == "q":
            stack.append(scale)
        elif operator == "Q" and stack:
            scale = stack.pop()
        elif operator == "cm":
            a, b, c, d = (_number(value) for value in item.operands[:4])
            scale *= a * d - b * c
        elif (
            operator == "Do"
            and xobjects is not None
            and _is_image(xobjects, item.operands[0])
        ):
            covered += abs(scale)
    return min(covered / area, 1.0)


def _number(value: object) -> float:
    return float(cast("SupportsFloat", value))


def _is_image(xobjects: pikepdf.Object, name: pikepdf.Object) -> bool:
    target = xobjects.get(str(name))
    return target is not None and target.get("/Subtype") == "/Image"
