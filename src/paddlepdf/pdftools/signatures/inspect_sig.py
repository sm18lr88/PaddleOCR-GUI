"""Turn one pyhanko embedded signature into a JSON-ready validation finding."""

from typing import Final, cast

from pydantic import JsonValue
from pyhanko.pdf_utils.generic import ArrayObject
from pyhanko.sign.diff_analysis import ModificationLevel
from pyhanko.sign.validation import validate_pdf_signature
from pyhanko.sign.validation.errors import SignatureValidationError
from pyhanko.sign.validation.pdf_embedded import EmbeddedPdfSignature
from pyhanko.sign.validation.status import PdfSignatureStatus, SignatureCoverageLevel
from pyhanko_certvalidator import ValidationContext

_ALLOWED_LATER_CHANGES: Final = frozenset(
    {
        ModificationLevel.NONE,
        ModificationLevel.LTA_UPDATES,
        ModificationLevel.FORM_FILLING,
    }
)


def inspect_signature(
    signature: EmbeddedPdfSignature, context: ValidationContext, revisions: int
) -> dict[str, JsonValue]:
    base: dict[str, JsonValue] = {
        "field_name": signature.field_name,
        "sub_filter": str(_entry(signature, "/SubFilter") or ""),
        "byte_range": _byte_range(signature),
        "signed_revision": signature.signed_revision,
    }
    try:
        status = validate_pdf_signature(signature, context)
    except SignatureValidationError as error:
        problem = f"Signature could not be validated: {error}"
        failure: dict[str, JsonValue] = {
            "is_valid": False,
            "is_tampered": True,
            "trusted": False,
            "problems": [problem],
        }
        return base | failure
    problems, tampered = _problems(status, signature.signed_revision, revisions)
    details: dict[str, JsonValue] = {
        "signer_subject": _subject(status),
        "signing_time": (
            status.signer_reported_dt.isoformat() if status.signer_reported_dt else None
        ),
        "intact": status.intact,
        "cryptographically_valid": status.valid,
        "trusted": status.trusted,
        "coverage": status.coverage.name.lower() if status.coverage else "unknown",
        "covers_entire_file": status.coverage == SignatureCoverageLevel.ENTIRE_FILE,
        "modification_level": (
            status.modification_level.name.lower()
            if status.modification_level is not None
            else None
        ),
        "docmdp_ok": status.docmdp_ok,
        "is_valid": not problems,
        "is_tampered": tampered,
        "problems": list(problems),
        "summary": status.summary(),
    }
    return base | details


def _problems(
    status: PdfSignatureStatus, signed_revision: int, revisions: int
) -> tuple[list[str], bool]:
    problems: list[str] = []
    tampered = False
    if not status.intact:
        problems.append("Signed bytes were modified after signing (digest mismatch)")
        tampered = True
    if not status.valid:
        problems.append("Cryptographic signature does not verify")
    if status.coverage == SignatureCoverageLevel.ENTIRE_FILE:
        return problems, tampered
    if signed_revision >= revisions - 1:
        problems.append("Bytes were appended after the signature outside any revision")
        return problems, True
    if status.coverage != SignatureCoverageLevel.ENTIRE_REVISION:
        problems.append("Signature does not cover its whole revision")
        return problems, True
    level = status.modification_level
    if status.docmdp_ok is False or (
        level is not None and level not in _ALLOWED_LATER_CHANGES
    ):
        problems.append("Later incremental updates made disallowed changes")
        tampered = True
    return problems, tampered


def _subject(status: PdfSignatureStatus) -> str:
    return cast("str", status.signing_cert.subject.human_friendly)


def _entry(signature: EmbeddedPdfSignature, key: str) -> object:
    return cast("object", signature.sig_object.get(key))


def _byte_range(signature: EmbeddedPdfSignature) -> list[JsonValue]:
    value = _entry(signature, "/ByteRange")
    if not isinstance(value, ArrayObject):
        return []
    items = cast("list[object]", value)
    return [int(item) for item in items if isinstance(item, int)]
