"""Shared AcroForm field introspection used by the read/fill/create handlers."""

from collections.abc import Sequence
from enum import StrEnum

import pikepdf

from paddlepdf.pdftools.contract import PdfToolError

_FIELD_TYPE_NAMES = {
    "/Tx": "text",
    "/Btn": "button",
    "/Ch": "choice",
    "/Sig": "signature",
}


class FieldKind(StrEnum):
    TEXT = "text"
    CHECKBOX = "checkbox"
    RADIO = "radio"
    PUSHBUTTON = "pushbutton"
    CHOICE = "choice"
    SIGNATURE = "signature"
    UNKNOWN = "unknown"


_KIND_CHECKS: tuple[tuple[str, FieldKind], ...] = (
    ("is_text", FieldKind.TEXT),
    ("is_checkbox", FieldKind.CHECKBOX),
    ("is_radio_button", FieldKind.RADIO),
    ("is_pushbutton", FieldKind.PUSHBUTTON),
    ("is_choice", FieldKind.CHOICE),
)


def field_kind(field: pikepdf.AcroFormField) -> FieldKind:
    for attribute, kind in _KIND_CHECKS:
        if getattr(field, attribute):
            return kind
    if _FIELD_TYPE_NAMES.get(field.field_type) == "signature":
        return FieldKind.SIGNATURE
    return FieldKind.UNKNOWN


def field_value(field: pikepdf.AcroFormField, kind: FieldKind) -> str | bool | None:
    if kind in (FieldKind.CHECKBOX, FieldKind.RADIO):
        return bool(field.is_checked)
    text = field.value_as_string
    return text or None


def field_page_number(pdf: pikepdf.Pdf, field: pikepdf.AcroFormField) -> int | None:
    """Return the 1-based page index of the field's first widget annotation."""
    for annotation in pdf.acroform.get_annotations_for_field(field):
        page_ref = annotation.obj.get("/P")
        if page_ref is None:
            continue
        for index, page in enumerate(pdf.pages):
            if page.obj.objgen == page_ref.objgen:
                return index + 1
    return None


def checkbox_on_state(field: pikepdf.AcroFormField) -> str:
    """Find the widget's "on" appearance-state name (anything other than /Off)."""
    widget = field.obj
    appearance_dict = widget.get("/AP")
    normal = appearance_dict.get("/N") if appearance_dict is not None else None
    if normal is not None and hasattr(normal, "keys"):
        for key in normal:
            name = str(key)
            if name not in {"/Off", "Off"}:
                return name.removeprefix("/")
    return "Yes"


def find_field(pdf: pikepdf.Pdf, name: str) -> pikepdf.AcroFormField:
    matches: Sequence[pikepdf.AcroFormField] = (
        pdf.acroform.get_fields_with_qualified_name(name) if pdf.acroform.exists else []
    )
    if not matches:
        msg = f"Form field not found: {name!r}"
        raise PdfToolError(msg)
    return matches[0]
