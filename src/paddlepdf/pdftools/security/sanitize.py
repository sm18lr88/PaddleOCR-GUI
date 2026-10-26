"""Remove active content, attachments, metadata, and private data from a PDF."""

from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Annotated

import pikepdf
from pydantic import Field, JsonValue

from paddlepdf.pdftools.common import input_path, open_pdf, output_path, save_pdf
from paddlepdf.pdftools.contract import PdfToolError, ToolOutcome
from paddlepdf.pdftools.security._params import InputFile, InputPassword, OutputFile

_EXTERNAL_ACTIONS = frozenset(
    {"/Launch", "/URI", "/SubmitForm", "/ImportData", "/GoToR", "/GoToE"}
)


@dataclass(frozen=True, slots=True)
class _Options:
    scripts: bool
    external_actions: bool
    attachments: bool
    thumbnails: bool
    private_data: bool


@dataclass(slots=True)
class _Report:
    counts: Counter[str] = field(default_factory=Counter)
    removed: list[str] = field(default_factory=list)

    def drop(self, holder: pikepdf.Dictionary, key: str, kind: str, where: str) -> bool:
        if key not in holder:
            return False
        del holder[key]
        self.counts[kind] += 1
        self.removed.append(f"{where} {key}")
        return True


def _dicts(value: object) -> list[pikepdf.Dictionary]:
    if isinstance(value, pikepdf.Dictionary):
        return [value]
    if isinstance(value, pikepdf.Array):
        return [item for item in value if isinstance(item, pikepdf.Dictionary)]
    return []


def _action_kind(action: object, options: _Options) -> str | None:
    pending = _dicts(action)
    seen: set[tuple[int, int]] = set()
    while pending:
        node = pending.pop()
        if node.is_indirect:
            if node.objgen in seen:
                continue
            seen.add(node.objgen)
        subtype = str(node.get("/S", ""))
        if options.scripts and subtype == "/JavaScript":
            return "scripts"
        if options.external_actions and subtype in _EXTERNAL_ACTIONS:
            return "external_actions"
        pending.extend(_dicts(node.get("/Next")))
    return None


def _strip_actions(
    holder: pikepdf.Dictionary, where: str, options: _Options, report: _Report
) -> None:
    if options.scripts:
        report.drop(holder, "/AA", "scripts", where)
    kind = _action_kind(holder.get("/A"), options)
    if kind is not None:
        report.drop(holder, "/A", kind, where)


def _clean_catalog(
    root: pikepdf.Dictionary, options: _Options, report: _Report
) -> None:
    names = root.get("/Names")
    if options.scripts:
        report.drop(root, "/OpenAction", "scripts", "catalog")
        report.drop(root, "/AA", "scripts", "catalog")
        if isinstance(names, pikepdf.Dictionary):
            report.drop(names, "/JavaScript", "scripts", "catalog /Names")
        acroform = root.get("/AcroForm")
        if isinstance(acroform, pikepdf.Dictionary):
            report.drop(acroform, "/XFA", "scripts", "catalog /AcroForm")
    if options.attachments:
        if isinstance(names, pikepdf.Dictionary):
            report.drop(names, "/EmbeddedFiles", "attachments", "catalog /Names")
        report.drop(root, "/AF", "attachments", "catalog")
    if options.private_data:
        report.drop(root, "/PieceInfo", "private_data", "catalog")


def _is_attachment_annot(annot: object, options: _Options) -> bool:
    return (
        options.attachments
        and isinstance(annot, pikepdf.Dictionary)
        and str(annot.get("/Subtype", "")) == "/FileAttachment"
    )


def _clean_annots(
    annots: pikepdf.Array, where: str, options: _Options, report: _Report
) -> pikepdf.Array:
    kept = pikepdf.Array()
    for annot in annots:
        if _is_attachment_annot(annot, options):
            report.counts["attachments"] += 1
            report.removed.append(f"{where} /FileAttachment annotation")
            continue
        if isinstance(annot, pikepdf.Dictionary):
            _strip_actions(annot, f"{where} annotation", options, report)
        kept.append(annot)
    return kept


def _clean_page_keys(
    page_dict: pikepdf.Dictionary, where: str, options: _Options, report: _Report
) -> None:
    if options.thumbnails:
        report.drop(page_dict, "/Thumb", "thumbnails", where)
    if options.private_data:
        report.drop(page_dict, "/PieceInfo", "private_data", where)
    if options.scripts:
        report.drop(page_dict, "/AA", "scripts", where)


def _clean_pages(pdf: pikepdf.Pdf, options: _Options, report: _Report) -> None:
    for number, page in enumerate(pdf.pages, start=1):
        where = f"page {number}"
        page_dict = page.obj
        _clean_page_keys(page_dict, where, options, report)
        annots = page_dict.get("/Annots")
        if isinstance(annots, pikepdf.Array):
            page_dict.Annots = _clean_annots(annots, where, options, report)


def _clean_tree(
    start: object, child_key: str, where: str, options: _Options, report: _Report
) -> None:
    pending = _dicts(start)
    seen: set[tuple[int, int]] = set()
    while pending:
        node = pending.pop()
        if node.is_indirect:
            if node.objgen in seen:
                continue
            seen.add(node.objgen)
        _strip_actions(node, where, options, report)
        if child_key == "/Kids":
            pending.extend(_dicts(node.get("/Kids")))
        else:
            pending.extend(_dicts(node.get("/First")) + _dicts(node.get("/Next")))


def pdf_sanitize(
    input_file: InputFile,
    output_file: OutputFile,
    remove_metadata: Annotated[
        bool, Field(description="Strip /Info and XMP metadata.")
    ] = True,
    remove_attachments: Annotated[
        bool,
        Field(description="Remove embedded files and file-attachment annotations."),
    ] = True,
    remove_scripts: Annotated[
        bool,
        Field(description="Remove JavaScript, /OpenAction, /AA triggers, and XFA."),
    ] = True,
    remove_external_actions: Annotated[
        bool,
        Field(
            description="Remove Launch, URI, SubmitForm, ImportData, GoToR/E actions."
        ),
    ] = True,
    remove_thumbnails: Annotated[
        bool, Field(description="Remove page thumbnails.")
    ] = True,
    remove_private_data: Annotated[
        bool, Field(description="Remove /PieceInfo private application data.")
    ] = True,
    password: InputPassword = None,
) -> ToolOutcome:
    options = _Options(
        scripts=remove_scripts,
        external_actions=remove_external_actions,
        attachments=remove_attachments,
        thumbnails=remove_thumbnails,
        private_data=remove_private_data,
    )
    report = _Report()
    source = input_path(input_file)
    target = output_path(output_file, source)
    with open_pdf(source, password) as pdf:
        root, trailer = pdf.Root, pdf.trailer
        if not isinstance(root, pikepdf.Dictionary) or not isinstance(
            trailer, pikepdf.Dictionary
        ):
            msg = f"{source} has no document catalog; cannot sanitize"
            raise PdfToolError(msg)
        metadata_stripped = False
        if remove_metadata:
            metadata_stripped = report.drop(trailer, "/Info", "metadata", "trailer")
            metadata_stripped = (
                report.drop(root, "/Metadata", "metadata", "catalog")
                or metadata_stripped
            )
        _clean_catalog(root, options, report)
        _clean_pages(pdf, options, report)
        acroform = root.get("/AcroForm")
        if isinstance(acroform, pikepdf.Dictionary):
            _clean_tree(acroform.get("/Fields"), "/Kids", "form field", options, report)
        outlines = root.get("/Outlines")
        if isinstance(outlines, pikepdf.Dictionary):
            _clean_tree(
                outlines.get("/First"), "/First", "outline item", options, report
            )
        written = save_pdf(pdf, target)
    data: dict[str, JsonValue] = {
        "metadata_stripped": metadata_stripped,
        "attachments_removed": report.counts["attachments"],
        "scripts_removed": report.counts["scripts"],
        "external_actions_removed": report.counts["external_actions"],
        "thumbnails_removed": report.counts["thumbnails"],
        "private_data_removed": report.counts["private_data"],
        "output_bytes": Path(written).stat().st_size,
        "removed": [*report.removed],
    }
    return ToolOutcome(output_files=(written,), data=data)
