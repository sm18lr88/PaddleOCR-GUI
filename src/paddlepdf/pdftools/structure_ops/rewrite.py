"""Whole-document rewrites: xref repair, linearization, form/annotation flattening."""

from enum import StrEnum
from typing import Annotated, cast

import pikepdf
from pydantic import Field, JsonValue

from paddlepdf.pdftools.common import input_path, open_pdf, output_path
from paddlepdf.pdftools.contract import PdfToolError, ToolOutcome
from paddlepdf.pdftools.structure_ops._params import (
    InputFile,
    OutputFile,
    Password,
    encryption_warnings,
)


class FlattenMode(StrEnum):
    ALL = "all"
    PRINT = "print"
    SCREEN = "screen"


def _qpdf_warnings(pdf: pikepdf.Pdf) -> list[str]:
    warnings = cast("list[object]", pdf.get_warnings())
    return [str(warning) for warning in warnings]


def pdf_repair(
    input_file: InputFile,
    output_file: OutputFile,
    password: Password = None,
) -> ToolOutcome:
    source = input_path(input_file)
    target = output_path(output_file, source)
    try:
        pdf = pikepdf.open(source, password=password or "", attempt_recovery=True)
    except pikepdf.PasswordError as error:
        msg = f"Wrong or missing password for {source}"
        raise PdfToolError(msg) from error
    except pikepdf.PdfError as error:
        msg = f"PDF is too damaged to recover: {source}: {error}"
        raise PdfToolError(msg) from error
    with pdf:
        problems = _qpdf_warnings(pdf)
        pdf.save(target, object_stream_mode=pikepdf.ObjectStreamMode["generate"])
        warnings = encryption_warnings(pdf)
        page_count = len(pdf.pages)
    with pikepdf.open(target) as repaired:
        remaining = _qpdf_warnings(repaired)
    data: dict[str, JsonValue] = {
        "page_count": page_count,
        "problems_found": list[JsonValue](problems),
        "problems_after_repair": list[JsonValue](remaining),
        "repaired": bool(problems) and not remaining,
    }
    return ToolOutcome(output_files=(str(target),), data=data, warnings=warnings)


def pdf_linearize(
    input_file: InputFile,
    output_file: OutputFile,
    password: Password = None,
) -> ToolOutcome:
    source = input_path(input_file)
    target = output_path(output_file, source)
    with open_pdf(source, password) as pdf:
        pdf.save(target, linearize=True)
        warnings = encryption_warnings(pdf)
    with pikepdf.open(target) as result:
        data: dict[str, JsonValue] = {
            "linearized": result.is_linearized,
            "page_count": len(result.pages),
        }
    return ToolOutcome(output_files=(str(target),), data=data, warnings=warnings)


def _annotation_count(pdf: pikepdf.Pdf) -> int:
    total = 0
    for page in pdf.pages:
        annots = page.obj.get("/Annots")
        if isinstance(annots, pikepdf.Array):
            total += len(annots)
    return total


def _field_count(acroform: object) -> int:
    if not isinstance(acroform, pikepdf.Dictionary):
        return 0
    fields = acroform.get("/Fields")
    return len(fields) if isinstance(fields, pikepdf.Array) else 0


_NEVER_FLATTENED = frozenset({"/Link", "/Popup"})


def _unflattened_annotations(pdf: pikepdf.Pdf) -> int:
    return sum(
        1
        for page in pdf.pages
        for annot in page.get("/Annots", pikepdf.Array())
        if isinstance(annot, pikepdf.Dictionary)
        and str(annot.get("/Subtype")) not in _NEVER_FLATTENED
    )


def pdf_flatten(
    input_file: InputFile,
    output_file: OutputFile,
    mode: Annotated[
        FlattenMode,
        Field(
            description=(
                "Which annotations to burn in: 'all', only those flagged for "
                "'print', or only those visible on 'screen'."
            )
        ),
    ] = FlattenMode.ALL,
    password: Password = None,
) -> ToolOutcome:
    source = input_path(input_file)
    target = output_path(output_file, source)
    with open_pdf(source, password) as pdf:
        annotations_before = _annotation_count(pdf)
        acroform = pdf.Root.get("/AcroForm")
        fields = _field_count(acroform)
        if isinstance(acroform, pikepdf.Dictionary):
            # qpdf only regenerates appearances when NeedAppearances is set, and
            # widgets without an appearance would vanish when flattened.
            acroform.NeedAppearances = True
            pdf.generate_appearance_streams()
        pdf.flatten_annotations(mode.value)
        if "/AcroForm" in pdf.Root:
            del pdf.Root.AcroForm
        annotations_after = _annotation_count(pdf)
        unflattened = _unflattened_annotations(pdf)
        pdf.save(target)
        warnings = encryption_warnings(pdf)
    if unflattened:
        warnings = (
            *warnings,
            (
                f"{unflattened} annotation(s) have no appearance stream and could "
                "not be burned into page content; they remain as annotations."
            ),
        )
    data: dict[str, JsonValue] = {
        "form_fields_removed": fields,
        "annotations_before": annotations_before,
        "annotations_after": annotations_after,
        "mode": mode.value,
    }
    return ToolOutcome(output_files=(str(target),), data=data, warnings=warnings)
