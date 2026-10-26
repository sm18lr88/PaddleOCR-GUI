from enum import StrEnum
from typing import Annotated

import pikepdf
from pikepdf import Array, Dictionary, Name, Page
from pydantic import BaseModel, Field

from paddlepdf.pdftools.common import input_path, open_pdf, output_path, save_pdf
from paddlepdf.pdftools.contract import PdfToolError, ToolOutcome
from paddlepdf.pdftools.marking._annot_appearance import appearance
from paddlepdf.pdftools.marking._overlay import parse_color

_SUBTYPES = {
    "highlight": "/Highlight",
    "underline": "/Underline",
    "strikethrough": "/StrikeOut",
    "note": "/Text",
    "pen": "/Ink",
}
_TEXT_MARKUP = frozenset({"highlight", "underline", "strikethrough"})
_PRINT_FLAG = 4


class AnnotationKind(StrEnum):
    HIGHLIGHT = "highlight"
    UNDERLINE = "underline"
    STRIKETHROUGH = "strikethrough"
    NOTE = "note"
    PEN = "pen"


class AnnotationSpec(BaseModel):
    id: Annotated[
        str | None, Field(description="Stored as the annotation name (/NM).")
    ] = None
    type: Annotated[AnnotationKind, Field(description="Annotation kind.")]
    page: Annotated[int, Field(ge=1, description="1-based page number.")]
    x: Annotated[
        float, Field(description="Left edge in PDF points (bottom-left origin).")
    ]
    y: Annotated[
        float, Field(description="Bottom edge in PDF points (bottom-left origin).")
    ]
    w: Annotated[
        float | None, Field(description="Width (default 100; notes are 24).")
    ] = None
    h: Annotated[
        float | None, Field(description="Height (default 20; pen 100; notes 24).")
    ] = None
    color: Annotated[str, Field(description="#RRGGBB color.")] = "#ffff00"
    content: Annotated[str | None, Field(description="Popup text for notes.")] = None
    points: Annotated[
        list[tuple[float, float]] | None,
        Field(description="Pen stroke path in PDF points; default is a diagonal."),
    ] = None


def _rect(spec: AnnotationSpec) -> tuple[float, float, float, float]:
    if spec.type is AnnotationKind.NOTE:
        return spec.x, spec.y, spec.x + 24, spec.y + 24
    default_h = 100.0 if spec.type is AnnotationKind.PEN else 20.0
    return spec.x, spec.y, spec.x + (spec.w or 100.0), spec.y + (spec.h or default_h)


def _build(pdf: pikepdf.Pdf, spec: AnnotationSpec) -> Dictionary:
    left, bottom, right, top = _rect(spec)
    color = parse_color(spec.color)
    annot = Dictionary(
        Type=Name.Annot,
        Subtype=Name(_SUBTYPES[spec.type.value]),
        Rect=Array([left, bottom, right, top]),
        C=Array(list(color)),
        F=_PRINT_FLAG,
        AP=appearance(
            pdf, spec.type.value, (left, bottom, right, top), color, spec.points
        ),
    )
    if spec.id:
        annot.NM = pikepdf.String(spec.id)
    if spec.content is not None:
        annot.Contents = pikepdf.String(spec.content)
    if spec.type.value in _TEXT_MARKUP:
        annot.QuadPoints = Array([left, bottom, right, bottom, left, top, right, top])
    if spec.type is AnnotationKind.PEN:
        stroke = spec.points or [(left, bottom), (right, top)]
        annot.InkList = Array([Array([c for point in stroke for c in point])])
    return annot


def pdf_annotate(
    input_file: Annotated[str, Field(description="Source PDF path.")],
    output_file: Annotated[str, Field(description="Destination PDF path.")],
    annotations: Annotated[
        list[AnnotationSpec],
        Field(
            min_length=1, description="Annotations to add as real PDF /Annots entries."
        ),
    ],
    password: Annotated[
        str | None, Field(description="Password of an encrypted input.")
    ] = None,
) -> ToolOutcome:
    source = input_path(input_file)
    target = output_path(output_file, source)
    with open_pdf(source, password) as pdf:
        for spec in annotations:
            if spec.page > len(pdf.pages):
                count = len(pdf.pages)
                msg = f"Annotation page {spec.page} is outside 1-{count}"
                raise PdfToolError(msg)
        for spec in annotations:
            page = Page(pdf.pages[spec.page - 1])
            if "/Annots" not in page.obj:
                page.obj.Annots = pdf.make_indirect(Array())
            page.obj.Annots.append(pdf.make_indirect(_build(pdf, spec)))
        saved = save_pdf(pdf, target)
    return ToolOutcome(
        output_files=(saved,), data={"annotations_added": len(annotations)}
    )
