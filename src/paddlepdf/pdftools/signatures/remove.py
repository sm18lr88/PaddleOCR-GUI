"""pdf_remove_signatures: strip signature values, fields, widgets, and locks."""

from dataclasses import dataclass, field
from typing import Annotated

import pikepdf
from pydantic import Field

from paddlepdf.pdftools.common import input_path, open_pdf, output_path, save_pdf
from paddlepdf.pdftools.contract import ToolOutcome


@dataclass(slots=True)
class _Removal:
    drop_fields: bool
    signatures: int = 0
    fields: int = 0
    widgets: set[tuple[int, int]] = field(default_factory=set[tuple[int, int]])


def pdf_remove_signatures(
    input_file: Annotated[str, Field(description="Signed PDF to strip.")],
    output_file: Annotated[str, Field(description="Path for the unsigned PDF.")],
    remove_empty_signature_fields: Annotated[
        bool,
        Field(
            description=(
                "Delete signature fields and their widgets entirely; when "
                "false only the signature values are cleared, leaving empty fields."
            )
        ),
    ] = True,
    password: Annotated[
        str | None, Field(description="Password of an encrypted input PDF.")
    ] = None,
) -> ToolOutcome:
    source = input_path(input_file)
    target = output_path(output_file, source)
    removal = _Removal(drop_fields=remove_empty_signature_fields)
    with open_pdf(source, password) as pdf:
        acroform = pdf.Root.get("/AcroForm")
        if isinstance(acroform, pikepdf.Dictionary):
            fields_array = acroform.get("/Fields")
            if isinstance(fields_array, pikepdf.Array):
                _strip_fields(fields_array, removal)
            _tidy_acroform(pdf, acroform, removal)
        if removal.drop_fields:
            _strip_widgets(pdf, removal)
        for key in ("/Perms", "/DSS"):
            if key in pdf.Root:
                del pdf.Root[key]
        written = save_pdf(pdf, target)
    warnings = () if removal.signatures else ("No digital signatures were found",)
    return ToolOutcome(
        output_files=(written,),
        data={
            "signatures_removed": removal.signatures,
            "fields_removed": removal.fields,
        },
        warnings=warnings,
    )


def _is_signature_field(node: pikepdf.Dictionary) -> bool:
    if node.get("/FT") == pikepdf.Name.Sig:
        return True
    value = node.get("/V")
    return isinstance(value, pikepdf.Dictionary) and value.get("/Type") == (
        pikepdf.Name.Sig
    )


def _strip_fields(fields_array: pikepdf.Array, removal: _Removal) -> None:
    doomed = [
        index
        for index, item in enumerate(fields_array)
        if _process_field(item, removal)
    ]
    for index in reversed(doomed):
        del fields_array[index]


def _process_field(item: object, removal: _Removal) -> bool:
    if not isinstance(item, pikepdf.Dictionary):
        return False
    kids = item.get("/Kids")
    if not _is_signature_field(item):
        if isinstance(kids, pikepdf.Array):
            _strip_fields(kids, removal)
        return False
    if "/V" in item:
        removal.signatures += 1
        del item["/V"]
    if not removal.drop_fields:
        return False
    removal.fields += 1
    removal.widgets.add(item.objgen)
    if isinstance(kids, pikepdf.Array):
        removal.widgets.update(kid.objgen for kid in kids)
    return True


def _tidy_acroform(
    pdf: pikepdf.Pdf, acroform: pikepdf.Dictionary, removal: _Removal
) -> None:
    if "/SigFlags" in acroform:
        del acroform["/SigFlags"]
    fields_array = acroform.get("/Fields")
    empty = not isinstance(fields_array, pikepdf.Array) or len(fields_array) == 0
    if removal.drop_fields and empty:
        del pdf.Root["/AcroForm"]


def _strip_widgets(pdf: pikepdf.Pdf, removal: _Removal) -> None:
    for page in pdf.pages:
        annots = page.obj.get("/Annots")
        if not isinstance(annots, pikepdf.Array):
            continue
        doomed = [
            index
            for index, annot in enumerate(annots)
            if isinstance(annot, pikepdf.Dictionary)
            and (annot.objgen in removal.widgets or _is_signature_widget(annot))
        ]
        for index in reversed(doomed):
            del annots[index]
        if len(annots) == 0:
            del page.obj["/Annots"]


def _is_signature_widget(annot: pikepdf.Dictionary) -> bool:
    if annot.get("/Subtype") != pikepdf.Name.Widget:
        return False
    parent = annot.get("/Parent")
    target = parent if isinstance(parent, pikepdf.Dictionary) else annot
    return target.get("/FT") == pikepdf.Name.Sig
