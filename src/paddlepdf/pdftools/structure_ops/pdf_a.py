"""Best-effort PDF/A-2b conversion: XMP identification, sRGB intent, banned features."""

from operator import methodcaller
from typing import Final, cast

import pikepdf
from PIL import ImageCms
from pydantic import JsonValue

from paddlepdf.pdftools.common import input_path, open_pdf, output_path
from paddlepdf.pdftools.contract import ToolOutcome
from paddlepdf.pdftools.structure_ops._params import (
    InputFile,
    OutputFile,
    Password,
    encryption_warnings,
)

FORBIDDEN_ACTIONS: Final = frozenset(
    {
        "/JavaScript",
        "/Launch",
        "/Sound",
        "/Movie",
        "/ResetForm",
        "/ImportData",
        "/Hide",
        "/SetOCGState",
        "/Rendition",
        "/Trans",
        "/GoTo3DView",
    }
)
EMBEDDED_FONT_KEYS: Final = ("/FontFile", "/FontFile2", "/FontFile3")
ANNOT_PRINT_FLAG: Final = 4
ANNOT_FORBIDDEN_FLAGS: Final = 1 | 2 | 32
NOT_VALIDATED_WARNING: Final = (
    "PDF/A-2b conformance was NOT validated (fonts, transparency, colour spaces "
    "and embedded files are only partially checked); verify with veraPDF."
)


def _is_forbidden_action(action: object) -> bool:
    return (
        isinstance(action, pikepdf.Dictionary)
        and str(action.get("/S", "")) in FORBIDDEN_ACTIONS
    )


def _strip_document_scripts(root: pikepdf.Object) -> int:
    removed = 0
    names = root.get("/Names")
    if isinstance(names, pikepdf.Dictionary) and "/JavaScript" in names:
        del names.JavaScript
        removed += 1
    if "/AA" in root:
        del root.AA
        removed += 1
    if _is_forbidden_action(root.get("/OpenAction")):
        del root.OpenAction
        removed += 1
    return removed


def _fix_annotations(page: pikepdf.Dictionary) -> tuple[int, int]:
    """Drop forbidden actions and force the Print flag; return (actions, flags)."""
    actions = flags = 0
    annots = page.get("/Annots")
    if not isinstance(annots, pikepdf.Array):
        return actions, flags
    for annot in annots:
        if not isinstance(annot, pikepdf.Dictionary):
            continue
        if "/AA" in annot:
            del annot.AA
            actions += 1
        if _is_forbidden_action(annot.get("/A")):
            del annot.A
            actions += 1
        if str(annot.get("/Subtype", "")) == "/Popup":
            continue
        current = int(annot.get("/F", 0))
        wanted = (current | ANNOT_PRINT_FLAG) & ~ANNOT_FORBIDDEN_FLAGS
        if wanted != current:
            annot.F = wanted
            flags += 1
    return actions, flags


def _font_descriptor(font: pikepdf.Dictionary) -> object:
    descendants = font.get("/DescendantFonts")
    if isinstance(descendants, pikepdf.Array) and len(descendants) > 0:
        child = descendants[0]
        if isinstance(child, pikepdf.Dictionary):
            return child.get("/FontDescriptor")
    return font.get("/FontDescriptor")


def _is_font_embedded(font: pikepdf.Dictionary) -> bool:
    descriptor = _font_descriptor(font)
    return isinstance(descriptor, pikepdf.Dictionary) and any(
        name in descriptor for name in EMBEDDED_FONT_KEYS
    )


def _page_fonts(page: pikepdf.Object) -> pikepdf.Dictionary | None:
    resources = page.get("/Resources")
    fonts = (
        resources.get("/Font") if isinstance(resources, pikepdf.Dictionary) else None
    )
    return fonts if isinstance(fonts, pikepdf.Dictionary) else None


def _unembedded_font_names(fonts: pikepdf.Dictionary) -> set[str]:
    missing: set[str] = set()
    for key, font in fonts.items():
        if not isinstance(font, pikepdf.Dictionary):
            continue
        if str(font.get("/Subtype", "")) == "/Type3":
            continue
        if not _is_font_embedded(font):
            missing.add(str(font.get("/BaseFont", key)).lstrip("/"))
    return missing


def _unembedded_fonts(pdf: pikepdf.Pdf) -> list[str]:
    missing: set[str] = set()
    for page in pdf.pages:
        fonts = _page_fonts(page.obj)
        if fonts is not None:
            missing |= _unembedded_font_names(fonts)
    return sorted(missing)


def _srgb_icc() -> bytes:
    # createProfile returns a CmsProfile from an unstubbed C module; call it
    # dynamically. ImageCmsProfile accepts that object at runtime.
    profile = cast("str", methodcaller("createProfile", "sRGB")(ImageCms))
    return ImageCms.ImageCmsProfile(profile).tobytes()


def _add_srgb_intent(pdf: pikepdf.Pdf) -> bool:
    intents = pdf.Root.get("/OutputIntents")
    if isinstance(intents, pikepdf.Array) and any(
        isinstance(intent, pikepdf.Dictionary)
        and str(intent.get("/S", "")) == "/GTS_PDFA1"
        for intent in intents
    ):
        return False
    icc = pdf.make_stream(_srgb_icc(), N=3, Alternate=pikepdf.Name.DeviceRGB)
    intent = pikepdf.Dictionary(
        Type=pikepdf.Name.OutputIntent,
        S=pikepdf.Name.GTS_PDFA1,
        OutputConditionIdentifier=pikepdf.String("sRGB IEC61966-2.1"),
        Info=pikepdf.String("sRGB IEC61966-2.1"),
        DestOutputProfile=icc,
    )
    pdf.Root.OutputIntents = pikepdf.Array([intent])
    return True


def pdf_to_pdf_a(
    input_file: InputFile,
    output_file: OutputFile,
    password: Password = None,
) -> ToolOutcome:
    source = input_path(input_file)
    target = output_path(output_file, source)
    with open_pdf(source, password) as pdf:
        warnings = [NOT_VALIDATED_WARNING, *encryption_warnings(pdf)]
        actions = _strip_document_scripts(pdf.Root)
        flags = 0
        for page in pdf.pages:
            if "/AA" in page.obj:
                del page.obj.AA
                actions += 1
            page_actions, page_flags = _fix_annotations(page.obj)
            actions += page_actions
            flags += page_flags
        acroform = pdf.Root.get("/AcroForm")
        if isinstance(acroform, pikepdf.Dictionary) and bool(
            acroform.get("/NeedAppearances", False)
        ):
            pdf.generate_appearance_streams()
            acroform.NeedAppearances = False
        intent_added = _add_srgb_intent(pdf)
        with pdf.open_metadata(set_pikepdf_as_editor=False) as meta:
            meta["pdfaid:part"] = "2"
            meta["pdfaid:conformance"] = "B"
        fonts = _unembedded_fonts(pdf)
        if fonts:
            warnings.append(
                "Fonts are not embedded, which PDF/A forbids: " + ", ".join(fonts)
            )
        names = pdf.Root.get("/Names")
        if isinstance(names, pikepdf.Dictionary) and "/EmbeddedFiles" in names:
            warnings.append(
                "Embedded files were kept; PDF/A-2 allows only embedded PDF/A files."
            )
        pdf.save(target, fix_metadata_version=True)
    data: dict[str, JsonValue] = {
        "pdfa_part": 2,
        "pdfa_conformance": "B",
        "validated": False,
        "forbidden_actions_removed": actions,
        "annotation_flags_fixed": flags,
        "output_intent_added": intent_added,
        "unembedded_fonts": list[JsonValue](fonts),
    }
    return ToolOutcome(output_files=(str(target),), data=data, warnings=tuple(warnings))
